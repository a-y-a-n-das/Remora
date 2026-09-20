from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import (
    UploadInitRequest,
    UploadInitResponse,
    MemoryStatus,
    SearchRequest,
    SearchResponse,
    SearchResult,
    QueryRequest,
    QueryResponse,
    QueryResult,
    MemoryListItem,
    Source,
    Action,
)
from app.services import (
    generate_memory_id,
    validate_file,
    sanitize_filename,
    generate_presigned_upload_url,
    generate_presigned_download_url,
    voyage_embedding_service,
    s3_vectors_service,
    database_service,
    nemotron_service,
)
from app.core.logging import get_logger
from app.core.exceptions import ValidationError
from app.core.database import get_db
from app.core.config import get_settings
from app.models import Memory

logger = get_logger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

_upload_rate_limit = {}


def check_rate_limit(client_ip: str) -> None:
    from app.core.config import get_settings
    settings = get_settings()
    import time

    now = time.time()
    window = 60

    if client_ip not in _upload_rate_limit:
        _upload_rate_limit[client_ip] = []

    _upload_rate_limit[client_ip] = [
        t for t in _upload_rate_limit[client_ip] if now - t < window
    ]

    if len(_upload_rate_limit[client_ip]) >= settings.RATE_LIMIT_UPLOADS:
        raise ValidationError(
            "Rate limit exceeded. Please wait before uploading more images.",
            details={"retry_after_seconds": window},
        )

    _upload_rate_limit[client_ip].append(now)


@router.get("", response_model=list[MemoryListItem])
async def list_memories(db: AsyncSession = Depends(get_db)):
    memories = await database_service.get_memories(db)
    return [
        MemoryListItem(
            id=memory.id,
            filename=memory.original_filename,
            original_filename=memory.original_filename,
            mime_type=memory.mime_type,
            size=memory.size_bytes,
            size_bytes=memory.size_bytes,
            processing_status=memory.processing_status,
            processing_stage=memory.processing_stage,
            s3_key=memory.s3_key,
            uploaded_at=memory.created_at,
        )
        for memory in memories
    ]


@router.post("/upload", response_model=UploadInitResponse)
async def init_upload(request: Request, upload_request: UploadInitRequest, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    try:
        # Sanitize filename
        safe_filename = sanitize_filename(upload_request.filename)
        validate_file(safe_filename, upload_request.mime_type, upload_request.size_bytes)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)

    memory_id = generate_memory_id()
    upload_url, s3_key, expires_in = await generate_presigned_upload_url(
        memory_id, safe_filename, upload_request.mime_type
    )

    memory = Memory(
        id=memory_id,
        s3_key=s3_key,
        original_filename=safe_filename,
        mime_type=upload_request.mime_type,
        size_bytes=upload_request.size_bytes,
        processing_status="uploaded",
        processing_stage="uploaded",
    )
    db.add(memory)
    await db.flush()

    logger.info(
        "upload_initialized",
        memory_id=memory_id,
        filename=safe_filename,
        mime_type=upload_request.mime_type,
        size_bytes=upload_request.size_bytes,
        client_ip=client_ip,
    )

    return UploadInitResponse(
        memory_id=memory_id,
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=expires_in,
    )


@router.get("/{memory_id}/status", response_model=MemoryStatus)
async def get_memory_status(memory_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryStatus(
        memory_id=memory.id,
        processing_status=memory.processing_status,
        processing_stage=memory.processing_stage,
        original_filename=memory.original_filename,
        mime_type=memory.mime_type,
        size_bytes=memory.size_bytes,
        uploaded_at=memory.created_at,
        error_message=None,
    )


@router.get("/{memory_id}/download-url")
async def get_download_url(memory_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if not memory.s3_key:
        raise HTTPException(status_code=404, detail="Memory has no associated file")

    download_url = await generate_presigned_download_url(memory.s3_key)
    return {"download_url": download_url}


@router.post("/{memory_id}/trigger-processing")
async def trigger_processing(memory_id: str, db: AsyncSession = Depends(get_db)):
    """
    Trigger processing for an uploaded memory.
    Called by frontend after successful S3 upload to start the processing pipeline.
    """
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if memory.processing_status != "uploaded":
        logger.info(
            "trigger_processing_skipped_not_uploaded",
            memory_id=memory_id,
            current_status=memory.processing_status,
        )
        return {"status": "skipped", "reason": f"Memory status is {memory.processing_status}"}

    if not memory.s3_key:
        raise HTTPException(status_code=400, detail="Memory has no associated S3 key")

    settings = get_settings()
    if not settings.SQS_QUEUE_URL:
        # No SQS configured - process directly
        from app.workers.s3_events import S3EventRecord
        from app.workers.processor import process_memory_event

        event = S3EventRecord(
            message_id=f"trigger-{memory_id}",
            bucket=settings.S3_BUCKET,
            key=memory.s3_key,
            event_name="ObjectCreated:Put",
            memory_id=memory_id,
            event_time=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("trigger_processing_direct", memory_id=memory_id)
        success = await process_memory_event(event)
        return {"status": "processed" if success else "failed", "memory_id": memory_id}

    # SQS configured - enqueue for worker
    from app.core.aws_clients import get_async_sqs_client
    import json

    sqs_message = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": settings.AWS_REGION,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": settings.S3_BUCKET},
                    "object": {"key": memory.s3_key, "size": memory.size_bytes},
                },
            }
        ]
    }

    client = get_async_sqs_client()
    async with client as sqs:
        await sqs.send_message(
            QueueUrl=settings.SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message),
        )

    logger.info("trigger_processing_enqueued", memory_id=memory_id)
    return {"status": "enqueued", "memory_id": memory_id}


@router.post("/search", response_model=SearchResponse)
async def search_memories(search_request: SearchRequest, db: AsyncSession = Depends(get_db)):
    query = search_request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    limit = min(search_request.limit, 50)

    # Generate query embedding using Voyage Multimodal 3
    query_embedding = await voyage_embedding_service.get_text_embedding(query)
    if query_embedding is None:
        raise HTTPException(status_code=503, detail="Failed to generate query embedding")

    # Search S3 Vectors for similar memory IDs
    try:
        vector_results = await s3_vectors_service.query_vectors(
            query_vector=query_embedding,
            top_k=limit,
        )
    except Exception as e:
        logger.error("s3_vectors_query_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Vector search service unavailable")

    if not vector_results:
        return SearchResponse(results=[], query=query)

    # Extract memory IDs from vector results
    memory_ids = [result["memory_id"] for result in vector_results]

    # Create a map of memory_id -> distance for relevance scoring
    distance_map = {result["memory_id"]: result.get("distance", 0.0) for result in vector_results}

    # Fetch memory records from Neon
    result = await database_service.get_memories_by_ids(db, memory_ids)
    memories = result if result else []

    # Build search results preserving the order from vector search
    search_results = []
    for memory_id in memory_ids:
        memory = next((m for m in memories if m.id == memory_id), None)
        if not memory:
            # Memory ID from S3 Vectors but missing from Neon - skip
            continue

        search_results.append(
            SearchResult(
                memory_id=memory.id,
                score=distance_map.get(memory_id, 0.0),
                ocr_text=memory.ocr_text,
                s3_key=memory.s3_key,
                original_filename=memory.original_filename,
                uploaded_at=memory.created_at,
            )
        )

    return SearchResponse(results=search_results, query=query)


@router.post("/query", response_model=QueryResponse)
async def query_memories(query_request: QueryRequest, db: AsyncSession = Depends(get_db)):
    query = query_request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    limit = min(query_request.limit, 10)

    # Generate query embedding using Voyage Multimodal 3
    query_embedding = await voyage_embedding_service.get_text_embedding(query)
    if query_embedding is None:
        raise HTTPException(status_code=503, detail="Failed to generate query embedding")

    # Search S3 Vectors for similar memory IDs
    try:
        vector_results = await s3_vectors_service.query_vectors(
            query_vector=query_embedding,
            top_k=limit,
        )
    except Exception as e:
        logger.error("s3_vectors_query_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Vector search service unavailable")

    if not vector_results:
        return QueryResponse(query=query, answer="I couldn't find any relevant memories for your query.", sources=[])

    # Extract memory IDs from vector results
    memory_ids = [result["memory_id"] for result in vector_results]

    # Create a map of memory_id -> distance for relevance scoring
    distance_map = {result["memory_id"]: result.get("distance", 0.0) for result in vector_results}

    # Fetch memory records from Neon
    result = await database_service.get_memories_by_ids(db, memory_ids)
    memories = result if result else []

    if not memories:
        return QueryResponse(
            query=query,
            answer="I found some relevant memories but couldn't retrieve their details from the database.",
            sources=[],
        )

    # Prepare memories with S3 image data for Nemotron
    enriched_memories = []
    for memory_id in memory_ids:
        memory = next((m for m in memories if m.id == memory_id), None)
        if not memory:
            continue

        distance = distance_map.get(memory_id, 0.0)
        enriched_memories.append({
            "memory_id": memory.id,
            "distance": distance,
            "ocr_text": memory.ocr_text or "",
            "s3_key": memory.s3_key,
            "original_filename": memory.original_filename or "unknown",
        })

    # DIAGNOSTIC LOGGING - candidates before Nemotron
    candidate_summaries = []
    for em in enriched_memories:
        ocr_preview = (em.get("ocr_text", "") or "")[:300]
        candidate_summaries.append({
            "memory_id": em.get("memory_id"),
            "distance": em.get("distance"),
            "original_filename": em.get("original_filename"),
            "ocr_preview": ocr_preview,
        })
    logger.info(
        "query_candidates_before_nemotron",
        user_query=query,
        conversation_history_length=len(query_request.conversation_history),
        conversation_history_last_5=query_request.conversation_history[-5:] if query_request.conversation_history else [],
        candidate_memory_ids=[em.get("memory_id") for em in enriched_memories],
        candidates=candidate_summaries,
    )

    # Perform multimodal reasoning with Nemotron
    answer, selected_memory_ids, sources, actions = await nemotron_service.reason(
        query, enriched_memories, query_request.conversation_history
    )

    # Check if this is a fallback response (empty selected_memory_ids but answer present)
    is_fallback = answer is not None and len(selected_memory_ids) == 0

    if answer is None:
        raise HTTPException(status_code=503, detail="Reasoning service unavailable")

    # Debug logging
    logger.info(
        "query_nemotron_result",
        selected_memory_ids=selected_memory_ids,
        selected_count=len(selected_memory_ids),
        candidate_count=len(enriched_memories),
    )

    # Deduplicate selected_memory_ids while preserving order
    seen = set()
    unique_selected_ids = []
    for mid in selected_memory_ids:
        if mid not in seen:
            seen.add(mid)
            unique_selected_ids.append(mid)

    # Build source results - ONLY include memories selected by Nemotron as relevant
    source_results = []
    for memory_id in unique_selected_ids:
        memory = next((m for m in memories if m.id == memory_id), None)
        if not memory:
            logger.warning("selected_memory_not_found_in_candidates", memory_id=memory_id)
            continue

        source_results.append(
            QueryResult(
                memory_id=memory.id,
                score=distance_map.get(memory.id, 0.0),
                ocr_text=memory.ocr_text,
                s3_key=memory.s3_key,
                original_filename=memory.original_filename,
                uploaded_at=memory.created_at,
            )
        )

    logger.info(
        "query_response_built",
        selected_memories_count=len(source_results),
        selected_memory_ids=[m.memory_id for m in source_results],
    )

    # Convert sources from agent format to Source schema
    source_objects = [
        Source(
            title=s.get("title", ""),
            url=s.get("url", ""),
            description=s.get("description"),
        )
        for s in sources
        if s.get("url")
    ]

    # Convert actions from agent format to Action schema
    action_objects = [
        Action(
            type=a.get("type", "google_calendar"),
            title=a.get("title", ""),
            url=a.get("url", ""),
            status=a.get("status", "prepared"),
        )
        for a in actions
        if a.get("url")
    ]

    return QueryResponse(
        query=query,
        answer=answer,
        selected_memory_ids=unique_selected_ids,
        selected_memories=source_results,
        sources=source_objects,
        actions=action_objects,
        is_fallback=is_fallback,
    )
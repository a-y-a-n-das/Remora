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
)
from app.services import (
    generate_memory_id,
    validate_file,
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


@router.post("/upload", response_model=UploadInitResponse)
async def init_upload(request: Request, upload_request: UploadInitRequest, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    try:
        validate_file(upload_request.filename, upload_request.mime_type, upload_request.size_bytes)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)

    memory_id = generate_memory_id()
    upload_url, s3_key, expires_in = await generate_presigned_upload_url(
        memory_id, upload_request.filename, upload_request.mime_type
    )

    memory = Memory(
        id=memory_id,
        s3_key=s3_key,
        original_filename=upload_request.filename,
        mime_type=upload_request.mime_type,
        size_bytes=upload_request.size_bytes,
        processing_status="uploaded",
        moderation_status="pending",
    )
    db.add(memory)
    await db.flush()

    logger.info(
        "upload_initialized",
        memory_id=memory_id,
        filename=upload_request.filename,
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
        moderation_status=memory.moderation_status,
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


@router.post("/search", response_model=SearchResponse)
async def search_memories(search_request: SearchRequest, db: AsyncSession = Depends(get_db)):
    query = search_request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    limit = min(search_request.limit, 50)

    # Generate query embedding using Voyage Multimodal 3.5
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

    # Generate query embedding using Voyage Multimodal 3.5
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

    # Perform multimodal reasoning with Nemotron
    answer = await nemotron_service.reason(query, enriched_memories)

    if answer is None:
        raise HTTPException(status_code=503, detail="Reasoning service unavailable")

    # Build source results
    sources = []
    for memory_id in memory_ids:
        memory = next((m for m in memories if m.id == memory_id), None)
        if not memory:
            continue

        sources.append(
            QueryResult(
                memory_id=memory.id,
                score=distance_map.get(memory.id, 0.0),
                ocr_text=memory.ocr_text,
                s3_key=memory.s3_key,
                original_filename=memory.original_filename,
                uploaded_at=memory.created_at,
            )
        )

    return QueryResponse(query=query, answer=answer, sources=sources)
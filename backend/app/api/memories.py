from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import UploadInitRequest, UploadInitResponse, MemoryStatus
from app.services import (
    generate_memory_id,
    validate_file,
    generate_presigned_upload_url,
    generate_presigned_download_url,
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
import os
import uuid
from datetime import datetime, timedelta
from app.core.aws_clients import get_s3_client, get_async_s3_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import ValidationError

logger = get_logger(__name__)


ALLOWED_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and remove dangerous characters."""
    # Remove directory components
    filename = os.path.basename(filename)
    # Remove null bytes
    filename = filename.replace("\x00", "")
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename


def generate_memory_id() -> str:
    return f"mem_{uuid.uuid4().hex[:16]}"


def get_s3_key(memory_id: str, mime_type: str) -> str:
    ext = ALLOWED_EXTENSIONS.get(mime_type, ".bin")
    return f"memories/{memory_id}/original{ext}"


def validate_file(filename: str, mime_type: str, size_bytes: int) -> None:
    settings = get_settings()

    if not filename or not filename.strip():
        raise ValidationError("Filename is required")

    if not mime_type or not mime_type.strip():
        raise ValidationError("MIME type is required")

    if size_bytes <= 0:
        raise ValidationError("File size must be greater than zero")

    if size_bytes > settings.max_file_size_bytes:
        raise ValidationError(
            f"File too large: {size_bytes} bytes (max {settings.max_file_size_bytes})",
            details={"max_size_mb": settings.MAX_FILE_SIZE_MB},
        )

    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"MIME type not allowed: {mime_type}",
            details={"allowed_types": settings.ALLOWED_MIME_TYPES},
        )


async def generate_presigned_upload_url(
    memory_id: str,
    filename: str,
    mime_type: str,
) -> tuple[str, str, int]:
    settings = get_settings()
    s3_key = get_s3_key(memory_id, mime_type)

    client = get_async_s3_client()
    async with client as s3:
        url = await s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": s3_key,
                "ContentType": mime_type,
            },
            ExpiresIn=settings.PRESIGNED_URL_EXPIRY_SECONDS,
        )

    logger.info(
        "presigned_url_generated",
        memory_id=memory_id,
        s3_key=s3_key,
        expires_in=settings.PRESIGNED_URL_EXPIRY_SECONDS,
    )

    return url, s3_key, settings.PRESIGNED_URL_EXPIRY_SECONDS


async def generate_presigned_download_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    settings = get_settings()
    client = get_async_s3_client()
    async with client as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
    return url


async def delete_s3_object(s3_key: str) -> bool:
    settings = get_settings()
    client = get_async_s3_client()
    async with client as s3:
        try:
            await s3.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            logger.info("s3_object_deleted", s3_key=s3_key)
            return True
        except Exception as e:
            logger.error("s3_delete_failed", s3_key=s3_key, error=str(e))
            return False


async def check_s3_object_exists(s3_key: str) -> bool:
    settings = get_settings()
    client = get_async_s3_client()
    async with client as s3:
        try:
            await s3.head_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            return True
        except Exception:
            return False

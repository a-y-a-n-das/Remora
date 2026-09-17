from fastapi import APIRouter
from app.core.aws_clients import get_s3_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    settings = get_settings()
    checks = {}

    try:
        s3 = get_s3_client()
        if settings.S3_BUCKET:
            s3.head_bucket(Bucket=settings.S3_BUCKET)
        checks["s3"] = "ok"
    except Exception as e:
        checks["s3"] = f"error: {str(e)[:100]}"

    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    return {"status": "ready"}
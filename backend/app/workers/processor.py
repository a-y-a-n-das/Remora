import asyncio
import sys
import time
from datetime import datetime, timezone

from app.core.aws_clients import get_async_s3_client, get_async_sqs_client
from app.core.config import get_settings
from app.core.database import close_database, get_db_session, init_database
from app.core.logging import get_logger
from app.services import (
    database_service,
    s3_vectors_service,
    textract_service,
    voyage_embedding_service,
)
from app.workers.s3_events import (
    S3EventParseError,
    S3EventRecord,
    extract_s3_records_from_sqs_message,
)

logger = get_logger(__name__)


class ProcessingError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        self.retryable = retryable
        super().__init__(message)


async def download_image_from_s3(s3_bucket: str, s3_key: str) -> bytes | None:
    client = get_async_s3_client()
    async with client as s3:
        try:
            response = await s3.get_object(Bucket=s3_bucket, Key=s3_key)
            return await response["Body"].read()
        except Exception as e:
            logger.error("s3_download_failed", s3_key=s3_key, error=str(e))
            return None


# Valid stage progression order
STAGE_ORDER = ["ocr", "embedding", "indexing", "ready"]

def validate_stage_transition(current_stage: str | None, new_stage: str, allow_recovery: bool = False) -> bool:
    """Ensure stage transitions only move forward.

    Args:
        current_stage: Current processing stage
        new_stage: Target processing stage
        allow_recovery: If True, allow resetting to 'ocr' from any stage (for crash recovery)
    """
    if current_stage is None:
        return new_stage == "ocr"
    if allow_recovery and new_stage == "ocr":
        # Allow recovery reset to initial stage
        return True
    try:
        current_idx = STAGE_ORDER.index(current_stage)
        new_idx = STAGE_ORDER.index(new_stage)
        return new_idx >= current_idx
    except ValueError:
        return False


async def process_memory_event(event: S3EventRecord) -> bool:
    memory_id = event.memory_id
    s3_bucket = event.bucket
    s3_key = event.key

    start_time = time.time()
    settings = get_settings()
    stale_threshold = settings.PROCESSING_STALE_THRESHOLD_SECONDS

    logger.info(
        "processing_started",
        memory_id=memory_id,
        bucket=s3_bucket,
        key=s3_key,
        event_name=event.event_name,
    )

    async with get_db_session() as db:
        try:
            # Check current status for idempotency AND recovery
            existing_memory = await database_service.get_memory(db, memory_id)
            recovery_mode = False
            if existing_memory:
                current_status = existing_memory.processing_status
                current_stage = existing_memory.processing_stage
                if current_status == "ready":
                    logger.info("memory_already_ready_skipping", memory_id=memory_id)
                    return True
                if current_status == "processing":
                    # Check if processing is stale (worker crashed mid-processing)
                    now = datetime.now(timezone.utc)
                    updated_at = existing_memory.updated_at
                    if updated_at:
                        elapsed = (now - updated_at).total_seconds()
                        if elapsed < stale_threshold:
                            # Recently updated - likely a duplicate SQS delivery
                            logger.info(
                                "memory_processing_recently_updated_skipping",
                                memory_id=memory_id,
                                current_stage=current_stage,
                                elapsed_seconds=elapsed,
                            )
                            return True
                        else:
                            # Stale processing - allow recovery
                            logger.warning(
                                "memory_processing_stale_allowing_recovery",
                                memory_id=memory_id,
                                current_stage=current_stage,
                                elapsed_seconds=elapsed,
                                stale_threshold=stale_threshold,
                            )
                            # Reset to ocr stage for full reprocessing
                            # S3 Vectors upsert is idempotent by memory_id
                            recovery_mode = True
                    else:
                        # No updated_at - assume stale and allow recovery
                        logger.warning(
                            "memory_processing_no_timestamp_allowing_recovery",
                            memory_id=memory_id,
                        )
                        recovery_mode = True
                if current_status == "failed":
                    # Allow retry for failed memories
                    logger.info("memory_failed_retrying", memory_id=memory_id)

            # Update status in Neon - stage: ocr
            await database_service.update_memory_status(db, memory_id, "processing", processing_stage="ocr")

            image_bytes = await download_image_from_s3(s3_bucket, s3_key)
            if not image_bytes:
                raise ProcessingError("Failed to download image from S3", retryable=True)

            ocr_text = textract_service.extract_text(s3_bucket, s3_key)

            # Persist OCR text to Neon
            await database_service.update_ocr_text(db, memory_id, ocr_text)

            # Validate and update stage to embedding
            if not validate_stage_transition("ocr", "embedding", allow_recovery=recovery_mode):
                raise ProcessingError("Invalid stage transition: ocr -> embedding", retryable=False)
            await database_service.update_memory_status(db, memory_id, "processing", processing_stage="embedding")

            embedding = await voyage_embedding_service.get_image_embedding(image_bytes, ocr_text)

            # Validate and update stage to indexing
            if not validate_stage_transition("embedding", "indexing", allow_recovery=recovery_mode):
                raise ProcessingError("Invalid stage transition: embedding -> indexing", retryable=False)
            await database_service.update_memory_status(db, memory_id, "processing", processing_stage="indexing")

            # Upsert vector to S3 Vectors
            s3_vectors_success = await s3_vectors_service.upsert_vector(
                memory_id,
                embedding,
                metadata={"content_type": "image"},
            )
            if not s3_vectors_success:
                raise ProcessingError("Failed to upsert vector to S3 Vectors", retryable=True)

            # Validate and update stage to ready
            if not validate_stage_transition("indexing", "ready", allow_recovery=recovery_mode):
                raise ProcessingError("Invalid stage transition: indexing -> ready", retryable=False)
            await database_service.update_memory_status(
                db, memory_id, "ready", processing_stage="ready"
            )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "processing_completed",
                memory_id=memory_id,
                has_ocr=bool(ocr_text),
                has_embedding=bool(embedding),
                duration_ms=duration_ms,
            )
            return True

        except ProcessingError:
            await database_service.update_memory_status(
                db,
                memory_id,
                "failed",
                error_message=str(sys.exc_info()[1]),
                processing_stage="failed",
            )
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "processing_failed",
                memory_id=memory_id,
                error=str(e),
                duration_ms=duration_ms,
            )
            await database_service.update_memory_status(
                db, memory_id, "failed", error_message=str(e), processing_stage="failed"
            )
            return False


async def run_worker():
    settings = get_settings()

    if not settings.SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL not configured, worker cannot start")
        return

    init_database()
    logger.info(
        "worker_starting",
        queue_url=settings.SQS_QUEUE_URL,
        max_messages=settings.SQS_MAX_MESSAGES,
        wait_time=settings.SQS_WAIT_TIME_SECONDS,
        visibility_timeout=settings.SQS_VISIBILITY_TIMEOUT_SECONDS,
    )

    sqs = get_async_sqs_client()

    try:
        async with sqs as client:
            while True:
                try:
                    response = await client.receive_message(
                        QueueUrl=settings.SQS_QUEUE_URL,
                        MaxNumberOfMessages=settings.SQS_MAX_MESSAGES,
                        WaitTimeSeconds=settings.SQS_WAIT_TIME_SECONDS,
                        VisibilityTimeout=settings.SQS_VISIBILITY_TIMEOUT_SECONDS,
                        MessageAttributeNames=["All"],
                    )

                    messages = response.get("Messages", [])

                    if not messages:
                        continue

                    for message in messages:
                        receipt_handle = message.get("ReceiptHandle")
                        message_id = message.get("MessageId", "unknown")

                        try:
                            event_records = extract_s3_records_from_sqs_message(message)
                        except S3EventParseError:
                            logger.warning(
                                "malformed_message_deleted",
                                message_id=message_id,
                            )
                            await client.delete_message(
                                QueueUrl=settings.SQS_QUEUE_URL,
                                ReceiptHandle=receipt_handle,
                            )
                            continue

                        all_processed = True
                        for event in event_records:
                            try:
                                success = await process_memory_event(event)
                                if not success:
                                    all_processed = False
                            except ProcessingError as e:
                                if e.retryable:
                                    all_processed = False
                                else:
                                    logger.warning(
                                        "non_retryable_error_deleting_message",
                                        message_id=message_id,
                                        memory_id=event.memory_id,
                                        error=str(e),
                                    )

                        if all_processed:
                            await client.delete_message(
                                QueueUrl=settings.SQS_QUEUE_URL,
                                ReceiptHandle=receipt_handle,
                            )
                            logger.info(
                                "message_deleted",
                                message_id=message_id,
                                records_count=len(event_records),
                            )
                        else:
                            logger.warning(
                                "message_not_deleted_will_retry",
                                message_id=message_id,
                                records_count=len(event_records),
                            )

                except asyncio.CancelledError:
                    logger.info("worker_cancelled")
                    break
                except Exception as e:
                    logger.exception(
                        "worker_loop_error",
                        error=str(e),
                    )
                    await asyncio.sleep(5)
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(run_worker())

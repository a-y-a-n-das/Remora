import asyncio
import sys
import time
from typing import Optional
from app.core.aws_clients import get_async_sqs_client, get_async_s3_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.database import get_db_session
from app.workers.s3_events import (
    extract_s3_records_from_sqs_message,
    S3EventRecord,
    S3EventParseError,
)
from app.services import (
    textract_service,
    voyage_embedding_service,
    opensearch_service,
    database_service,
)

logger = get_logger(__name__)


class ProcessingError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        self.retryable = retryable
        super().__init__(message)


async def download_image_from_s3(s3_bucket: str, s3_key: str) -> Optional[bytes]:
    settings = get_settings()
    client = get_async_s3_client()
    async with client as s3:
        try:
            response = await s3.get_object(Bucket=s3_bucket, Key=s3_key)
            return await response["Body"].read()
        except Exception as e:
            logger.error("s3_download_failed", s3_key=s3_key, error=str(e))
            return None


async def process_memory_event(event: S3EventRecord) -> bool:
    memory_id = event.memory_id
    s3_bucket = event.bucket
    s3_key = event.key

    start_time = time.time()
    logger.info(
        "processing_started",
        memory_id=memory_id,
        bucket=s3_bucket,
        key=s3_key,
        event_name=event.event_name,
    )

    async with get_db_session() as db:
        try:
            # Update status in both OpenSearch and Neon
            opensearch_service.update_memory_status(memory_id, "processing")
            await database_service.update_memory_status(db, memory_id, "processing")

            image_bytes = await download_image_from_s3(s3_bucket, s3_key)
            if not image_bytes:
                raise ProcessingError("Failed to download image from S3", retryable=True)

            ocr_text = textract_service.extract_text(s3_bucket, s3_key)

            # Persist OCR text to Neon
            await database_service.update_ocr_text(db, memory_id, ocr_text)

            embedding = await voyage_embedding_service.get_image_embedding(
                image_bytes, ocr_text
            )

            document = {
                "memory_id": memory_id,
                "s3_key": s3_key,
                "file": {
                    "original_filename": s3_key.split("/")[-1],
                    "mime_type": "image/unknown",
                    "size_bytes": len(image_bytes),
                },
                "time": {
                    "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "captured_at": None,
                },
                "text": {"ocr": ocr_text or ""},
                "embedding": embedding or [],
                "processing": {"status": "ready", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                "moderation": {"status": "approved", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            }

            success = opensearch_service.index_memory(document)
            if not success:
                raise ProcessingError("Failed to index memory in OpenSearch", retryable=True)

            # Update status to ready in both stores
            await database_service.update_memory_status(
                db, memory_id, "ready", moderation_status="approved"
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
            opensearch_service.update_memory_status(memory_id, "failed", error_message=str(sys.exc_info()[1]))
            await database_service.update_memory_status(db, memory_id, "failed", error_message=str(sys.exc_info()[1]))
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("processing_failed", memory_id=memory_id, error=str(e), duration_ms=duration_ms)
            opensearch_service.update_memory_status(memory_id, "failed", error_message=str(e))
            await database_service.update_memory_status(db, memory_id, "failed", error_message=str(e))
            return False


async def run_worker():
    settings = get_settings()

    if not settings.SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL not configured, worker cannot start")
        return

    if not opensearch_service.is_available():
        logger.warning("OpenSearch not configured, worker will fail on indexing")

    logger.info(
        "worker_starting",
        queue_url=settings.SQS_QUEUE_URL,
        max_messages=settings.SQS_MAX_MESSAGES,
        wait_time=settings.SQS_WAIT_TIME_SECONDS,
        visibility_timeout=settings.SQS_VISIBILITY_TIMEOUT_SECONDS,
    )

    sqs = get_async_sqs_client()

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
                logger.error(
                    "worker_loop_error",
                    error=str(e),
                )
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_worker())
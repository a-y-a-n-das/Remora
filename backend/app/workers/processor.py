import asyncio
import time
from app.core.aws_clients import get_async_sqs_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.workers.s3_events import (
    extract_s3_records_from_sqs_message,
    S3EventRecord,
    S3EventParseError,
)

logger = get_logger(__name__)


async def process_memory_event(event: S3EventRecord) -> bool:
    start_time = time.time()
    logger.info(
        "processing_started",
        memory_id=event.memory_id,
        bucket=event.bucket,
        key=event.key,
        event_name=event.event_name,
    )

    try:
        await asyncio.sleep(0.1)

        logger.info(
            "placeholder_processing_completed",
            memory_id=event.memory_id,
            duration_ms=int((time.time() - start_time) * 1000),
        )
        return True

    except Exception as e:
        logger.error(
            "processing_failed",
            memory_id=event.memory_id,
            error=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
        )
        return False


async def run_worker():
    settings = get_settings()

    if not settings.SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL not configured, worker cannot start")
        return

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
                        success = await process_memory_event(event)
                        if not success:
                            all_processed = False

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
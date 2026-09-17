import json
import urllib.parse
import re
from dataclasses import dataclass
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

MEMORY_KEY_PATTERN = re.compile(r"^memories/(mem_[a-f0-9]+)/original[^/]*\.[a-zA-Z0-9_.+-]+$")


@dataclass(frozen=True)
class S3EventRecord:
    message_id: str
    bucket: str
    key: str
    event_name: str
    memory_id: str
    event_time: str

    @property
    def is_object_created(self) -> bool:
        return self.event_name.startswith("ObjectCreated")


class S3EventParseError(Exception):
    def __init__(self, message: str, raw_record: dict = None):
        self.raw_record = raw_record
        super().__init__(message)


def parse_s3_key(key: str) -> Optional[str]:
    match = MEMORY_KEY_PATTERN.match(key)
    if match:
        return match.group(1)
    return None


def decode_s3_key(encoded_key: str) -> str:
    return urllib.parse.unquote_plus(encoded_key)


def extract_s3_event_record(record: dict, message_id: str) -> S3EventRecord:
    s3_info = record.get("s3", {})
    bucket = s3_info.get("bucket", {}).get("name")
    encoded_key = s3_info.get("object", {}).get("key")
    event_name = record.get("eventName", "")
    event_time = record.get("eventTime", "")

    if not bucket:
        raise S3EventParseError("Missing bucket in S3 event record", record)
    if not encoded_key:
        raise S3EventParseError("Missing object key in S3 event record", record)

    key = decode_s3_key(encoded_key)
    memory_id = parse_s3_key(key)

    if not memory_id:
        raise S3EventParseError(
            f"Object key does not match expected pattern: {key}",
            record,
        )

    logger.info(
        "s3_event_parsed",
        message_id=message_id,
        memory_id=memory_id,
        bucket=bucket,
        key=key,
        event_name=event_name,
    )

    return S3EventRecord(
        message_id=message_id,
        bucket=bucket,
        key=key,
        event_name=event_name,
        memory_id=memory_id,
        event_time=event_time,
    )


def parse_sqs_message_body(body: str) -> dict:
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise S3EventParseError(f"Invalid JSON in SQS message body: {e}")


def extract_s3_records_from_sqs_message(sqs_message: dict) -> list[S3EventRecord]:
    message_id = sqs_message.get("MessageId", "unknown")
    body = sqs_message.get("Body", "")

    try:
        notification = parse_sqs_message_body(body)
    except S3EventParseError as e:
        logger.warning(
            "sqs_message_parse_failed",
            message_id=message_id,
            error=str(e),
        )
        raise

    records = notification.get("Records", [])
    if not records:
        logger.warning(
            "sqs_message_no_records",
            message_id=message_id,
        )
        return []

    event_records = []
    for record in records:
        try:
            event_record = extract_s3_event_record(record, message_id)
            event_records.append(event_record)
        except S3EventParseError as e:
            logger.warning(
                "s3_event_record_parse_failed",
                message_id=message_id,
                error=str(e),
            )
            raise

    return event_records
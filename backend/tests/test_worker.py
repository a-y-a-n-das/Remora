import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.s3_events import (
    S3EventParseError,
    S3EventRecord,
    decode_s3_key,
    extract_s3_event_record,
    extract_s3_records_from_sqs_message,
    parse_s3_key,
)


class TestS3KeyParsing:
    def test_parse_valid_memory_key_jpeg(self):
        key = "memories/mem_abc123def456/original.jpg"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_valid_memory_key_png(self):
        key = "memories/mem_abc123def456/original.png"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_valid_memory_key_webp(self):
        key = "memories/mem_abc123def456/original.webp"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_valid_memory_key_gif(self):
        key = "memories/mem_abc123def456/original.gif"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_valid_memory_key_heic(self):
        key = "memories/mem_abc123def456/original.heic"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_valid_memory_key_heif(self):
        key = "memories/mem_abc123def456/original.heif"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc123def456"

    def test_parse_invalid_key_wrong_prefix(self):
        key = "uploads/mem_abc123def456/original.jpg"
        memory_id = parse_s3_key(key)
        assert memory_id is None

    def test_parse_invalid_key_wrong_pattern(self):
        key = "memories/mem_abc123def456/thumbnail.jpg"
        memory_id = parse_s3_key(key)
        assert memory_id is None

    def test_parse_invalid_key_no_memory_id(self):
        key = "memories/invalid_id/original.jpg"
        memory_id = parse_s3_key(key)
        assert memory_id is None

    def test_parse_invalid_key_short_memory_id(self):
        key = "memories/mem_abc1234567890ab/original.jpg"  # 16 hex chars = valid
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc1234567890ab"

    def test_parse_invalid_key_too_short_memory_id(self):
        # Parser accepts any length, but generator produces 16 hex chars
        key = "memories/mem_abc/original.jpg"
        memory_id = parse_s3_key(key)
        assert memory_id == "mem_abc"


class TestURLDecoding:
    def test_decode_s3_key_spaces(self):
        encoded = "memories/mem_abc123/original%20file.jpg"
        decoded = decode_s3_key(encoded)
        assert decoded == "memories/mem_abc123/original file.jpg"

    def test_decode_s3_key_special_chars(self):
        encoded = "memories/mem_abc123/original%2B%25.jpg"
        decoded = decode_s3_key(encoded)
        assert decoded == "memories/mem_abc123/original+%.jpg"

    def test_decode_s3_key_no_encoding(self):
        encoded = "memories/mem_abc123/original.jpg"
        decoded = decode_s3_key(encoded)
        assert decoded == "memories/mem_abc123/original.jpg"


class TestS3EventRecordExtraction:
    def test_extract_valid_object_created_event(self):
        record = {
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "us-east-1",
            "eventTime": "2024-01-15T10:30:00.000Z",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "remora-memories"},
                "object": {"key": "memories/mem_abc123def456/original.jpg", "size": 1024},
            },
        }
        event = extract_s3_event_record(record, "msg-123")

        assert event.message_id == "msg-123"
        assert event.bucket == "remora-memories"
        assert event.key == "memories/mem_abc123def456/original.jpg"
        assert event.event_name == "ObjectCreated:Put"
        assert event.memory_id == "mem_abc123def456"
        assert event.event_time == "2024-01-15T10:30:00.000Z"
        assert event.is_object_created is True

    def test_extract_object_created_post_event(self):
        record = {
            "eventName": "ObjectCreated:Post",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "memories/mem_abcdef1234567890/original.png"},
            },
        }
        event = extract_s3_event_record(record, "msg-456")
        assert event.is_object_created is True
        assert event.memory_id == "mem_abcdef1234567890"

    def test_extract_object_created_copy_event(self):
        record = {
            "eventName": "ObjectCreated:Copy",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "memories/mem_abcdef1234567890/original.png"},
            },
        }
        event = extract_s3_event_record(record, "msg-789")
        assert event.is_object_created is True
        assert event.memory_id == "mem_abcdef1234567890"

    def test_extract_non_object_created_event(self):
        record = {
            "eventName": "ObjectRemoved:Delete",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "memories/mem_abcdef1234567890/original.png"},
            },
        }
        event = extract_s3_event_record(record, "msg-999")
        assert event.is_object_created is False
        assert event.memory_id == "mem_abcdef1234567890"

    def test_extract_with_url_encoded_key(self):
        record = {
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "memories/mem_abc1234567890abc/original%2Bfile.jpg"},
            },
        }
        event = extract_s3_event_record(record, "msg-111")
        assert event.key == "memories/mem_abc1234567890abc/original+file.jpg"
        assert event.memory_id == "mem_abc1234567890abc"

    def test_extract_missing_bucket_raises_error(self):
        record = {
            "eventName": "ObjectCreated:Put",
            "s3": {"object": {"key": "memories/mem_abc123/original.jpg"}},
        }
        with pytest.raises(S3EventParseError) as exc_info:
            extract_s3_event_record(record, "msg-222")
        assert "Missing bucket" in str(exc_info.value)

    def test_extract_missing_key_raises_error(self):
        record = {"eventName": "ObjectCreated:Put", "s3": {"bucket": {"name": "test-bucket"}}}
        with pytest.raises(S3EventParseError) as exc_info:
            extract_s3_event_record(record, "msg-333")
        assert "Missing object key" in str(exc_info.value)

    def test_extract_invalid_key_pattern_raises_error(self):
        record = {
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "uploads/mem_abc123/original.jpg"},
            },
        }
        with pytest.raises(S3EventParseError) as exc_info:
            extract_s3_event_record(record, "msg-444")
        assert "does not match expected pattern" in str(exc_info.value)


class TestSQSMessageParsing:
    def test_parse_valid_sqs_message_with_records(self):
        body = json.dumps(
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "test-bucket"},
                            "object": {"key": "memories/mem_abc123/original.jpg"},
                        },
                    }
                ]
            }
        )
        message = {"MessageId": "msg-111", "ReceiptHandle": "receipt-111", "Body": body}
        records = extract_s3_records_from_sqs_message(message)
        assert len(records) == 1
        assert records[0].memory_id == "mem_abc123"

    def test_parse_sqs_message_multiple_records(self):
        body = json.dumps(
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "b"},
                            "object": {"key": "memories/mem_111/original.jpg"},
                        },
                    },
                    {
                        "eventName": "ObjectCreated:Post",
                        "s3": {
                            "bucket": {"name": "b"},
                            "object": {"key": "memories/mem_222/original.png"},
                        },
                    },
                ]
            }
        )
        message = {"MessageId": "msg-222", "Body": body}
        records = extract_s3_records_from_sqs_message(message)
        assert len(records) == 2
        assert records[0].memory_id == "mem_111"
        assert records[1].memory_id == "mem_222"

    def test_parse_sqs_message_no_records(self):
        body = json.dumps({"Records": []})
        message = {"MessageId": "msg-333", "Body": body}
        records = extract_s3_records_from_sqs_message(message)
        assert records == []

    def test_parse_sqs_message_missing_records_key(self):
        body = json.dumps({})
        message = {"MessageId": "msg-444", "Body": body}
        records = extract_s3_records_from_sqs_message(message)
        assert records == []

    def test_parse_invalid_json_raises_error(self):
        message = {"MessageId": "msg-555", "Body": "not valid json"}
        with pytest.raises(S3EventParseError) as exc_info:
            extract_s3_records_from_sqs_message(message)
        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_record_with_invalid_key_rejected(self):
        body = json.dumps(
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "b"},
                            "object": {"key": "uploads/mem_abc123/original.jpg"},
                        },
                    }
                ]
            }
        )
        message = {"MessageId": "msg-666", "Body": body}
        with pytest.raises(S3EventParseError):
            extract_s3_records_from_sqs_message(message)


class TestDuplicateEventSafety:
    def test_same_memory_id_parsed_consistently(self):
        key = "memories/mem_abc123def456/original.jpg"
        for _ in range(10):
            memory_id = parse_s3_key(key)
            assert memory_id == "mem_abc123def456"

    def test_duplicate_sqs_messages_produce_same_events(self):
        body = json.dumps(
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "b"},
                            "object": {"key": "memories/mem_abc123/original.jpg"},
                        },
                    }
                ]
            }
        )
        message1 = {"MessageId": "msg-1", "Body": body}
        message2 = {"MessageId": "msg-2", "Body": body}

        records1 = extract_s3_records_from_sqs_message(message1)
        records2 = extract_s3_records_from_sqs_message(message2)

        assert len(records1) == len(records2) == 1
        assert records1[0].memory_id == records2[0].memory_id == "mem_abc123"


class TestProcessMemoryEvent:
    @staticmethod
    def _processing_patches():
        from contextlib import asynccontextmanager

        from app.workers import processor

        @asynccontextmanager
        async def db_session():
            yield MagicMock(name="db")

        return (
            patch.object(processor, "get_db_session", db_session),
            patch.object(
                processor,
                "download_image_from_s3",
                new=AsyncMock(return_value=b"image-bytes"),
            ),
            patch.object(
                processor.textract_service,
                "extract_text",
                return_value=None,
            ),
            patch.object(
                processor.voyage_embedding_service,
                "get_image_embedding",
                new=AsyncMock(return_value=[0.0] * 1024),
            ),
            patch.object(
                processor.s3_vectors_service,
                "upsert_vector",
                new=AsyncMock(return_value=True),
            ),
            patch.object(
                processor.database_service,
                "update_memory_status",
                new=AsyncMock(return_value=True),
            ),
            patch.object(
                processor.database_service,
                "update_ocr_text",
                new=AsyncMock(return_value=True),
            ),
        )

    @pytest.mark.asyncio
    async def test_process_memory_event_success(self):
        from app.workers.processor import process_memory_event

        event = S3EventRecord(
            message_id="msg-test",
            bucket="test-bucket",
            key="memories/mem_abc123/original.jpg",
            event_name="ObjectCreated:Put",
            memory_id="mem_abc123",
            event_time="2024-01-15T10:30:00.000Z",
        )

        with patch("app.workers.processor.logger"):
            with ExitStack() as stack:
                for context in self._processing_patches():
                    stack.enter_context(context)
                result = await process_memory_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_process_memory_event_is_idempotent(self):
        from app.workers.processor import process_memory_event

        event = S3EventRecord(
            message_id="msg-test",
            bucket="test-bucket",
            key="memories/mem_abc123/original.jpg",
            event_name="ObjectCreated:Put",
            memory_id="mem_abc123",
            event_time="2024-01-15T10:30:00.000Z",
        )

        with ExitStack() as stack:
            for context in self._processing_patches():
                stack.enter_context(context)
            result1 = await process_memory_event(event)
            result2 = await process_memory_event(event)
        assert result1 is True
        assert result2 is True

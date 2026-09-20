import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError
from app.services.textract import TextractService, textract_service
from app.services.voyage import VoyageEmbeddingService, voyage_embedding_service
from app.services.s3_vectors import S3VectorsService, s3_vectors_service
from app.services.database import database_service
from app.workers.processor import ProcessingError, process_memory_event, validate_stage_transition
from app.workers.s3_events import S3EventRecord
from app.core.database import init_database, close_database, engine, async_session_maker


@pytest.fixture
def mock_db_session():
    """Mock the database session for testing."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def mock_session_maker(mock_db_session):
    """Create a mock session maker that returns our mock session as an async context manager."""
    def maker():
        return mock_db_session
    return maker


@pytest.fixture(autouse=True)
def setup_database(mock_session_maker):
    """Initialize the database with a mock session maker for all tests."""
    import app.core.database as db_module
    original_engine = db_module.engine
    original_session_maker = db_module.async_session_maker
    
    # Set up mock database
    db_module.engine = MagicMock()
    db_module.async_session_maker = mock_session_maker
    
    yield
    
    # Restore original
    db_module.engine = original_engine
    db_module.async_session_maker = original_session_maker


class TestTextractService:
    @pytest.fixture
    def textract_service(self):
        return TextractService()

    def test_extract_text_success(self, textract_service):
        mock_client = MagicMock()
        mock_client.detect_document_text.return_value = {
            "Blocks": [
                {"BlockType": "LINE", "Text": "AWS Invoice"},
                {"BlockType": "LINE", "Text": "Amount: $2,499"},
                {"BlockType": "WORD", "Text": "AWS"},
            ]
        }
        textract_service.client = mock_client

        result = textract_service.extract_text("test-bucket", "memories/mem_abc123/original.jpg")

        assert result == "AWS Invoice\nAmount: $2,499"
        mock_client.detect_document_text.assert_called_once_with(
            Document={"S3Object": {"Bucket": "test-bucket", "Name": "memories/mem_abc123/original.jpg"}}
        )

    def test_extract_text_no_text_found(self, textract_service):
        mock_client = MagicMock()
        mock_client.detect_document_text.return_value = {"Blocks": []}
        textract_service.client = mock_client

        result = textract_service.extract_text("test-bucket", "memories/mem_abc123/original.jpg")

        assert result is None

    def test_extract_text_invalid_parameter(self, textract_service):
        from botocore.exceptions import ClientError
        mock_client = MagicMock()
        # Set up the exceptions attribute properly
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.InvalidParameterException = ClientError
        error_response = {"Error": {"Code": "InvalidParameterException", "Message": "Invalid S3 object"}}
        mock_client.detect_document_text.side_effect = ClientError(error_response, "DetectDocumentText")
        textract_service.client = mock_client

        result = textract_service.extract_text("test-bucket", "memories/mem_abc123/original.jpg")

        assert result is None


class TestDatabaseService:
    @pytest.fixture
    def database_service(self):
        return database_service

    @pytest.fixture
    def mock_db(self):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()
        return mock_session

    @pytest.mark.asyncio
    async def test_update_ocr_text_success(self, database_service, mock_db):
        from app.models import Memory
        mock_memory = MagicMock(spec=Memory)
        mock_memory.id = "mem_abc123"
        mock_memory.ocr_text = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_memory
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await database_service.update_ocr_text(mock_db, "mem_abc123", "AWS Invoice\nAmount: $2,499")

        assert result is True
        assert mock_memory.ocr_text == "AWS Invoice\nAmount: $2,499"
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_ocr_text_empty_result(self, database_service, mock_db):
        from app.models import Memory
        mock_memory = MagicMock(spec=Memory)
        mock_memory.id = "mem_abc123"
        mock_memory.ocr_text = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_memory
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await database_service.update_ocr_text(mock_db, "mem_abc123", None)

        assert result is True
        assert mock_memory.ocr_text is None
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_ocr_text_empty_string(self, database_service, mock_db):
        from app.models import Memory
        mock_memory = MagicMock(spec=Memory)
        mock_memory.id = "mem_abc123"
        mock_memory.ocr_text = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_memory
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await database_service.update_ocr_text(mock_db, "mem_abc123", "")

        assert result is True
        assert mock_memory.ocr_text == ""
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_ocr_text_memory_not_found(self, database_service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await database_service.update_ocr_text(mock_db, "mem_nonexistent", "Some text")

        assert result is False
        mock_db.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_ocr_text_database_error(self, database_service, mock_db):
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection failed"))

        result = await database_service.update_ocr_text(mock_db, "mem_abc123", "Some text")

        assert result is False
        mock_db.flush.assert_not_awaited()


class TestProcessMemoryEvent:
    @pytest.fixture
    def event(self):
        return S3EventRecord(
            message_id="msg-123",
            bucket="test-bucket",
            key="memories/mem_abc123/original.jpg",
            event_name="ObjectCreated:Put",
            memory_id="mem_abc123",
            event_time="2024-01-15T10:30:00Z",
        )

    @pytest.mark.asyncio
    async def test_process_memory_event_success(self, event):
        # Create a mock memory object with processing_status and processing_stage
        mock_memory = MagicMock()
        mock_memory.processing_status = "uploaded"
        mock_memory.processing_stage = "uploaded"

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=True) as mock_s3v:
                        with patch.object(database_service, "update_ocr_text", return_value=True) as mock_ocr:
                            with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=mock_memory):
                                with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    mock_ocr.assert_awaited_once()
                                    mock_s3v.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_memory_event_download_failure(self, event):
        mock_memory = MagicMock()
        mock_memory.processing_status = "uploaded"
        mock_memory.processing_stage = "uploaded"

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = None

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                    with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                        with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=mock_memory):
                            with pytest.raises(ProcessingError):
                                await process_memory_event(event)

    @pytest.mark.asyncio
    async def test_process_memory_event_s3_vectors_failure(self, event):
        mock_memory = MagicMock()
        mock_memory.processing_status = "uploaded"
        mock_memory.processing_stage = "uploaded"

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=False):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=mock_memory):
                                    with pytest.raises(ProcessingError):
                                        await process_memory_event(event)

    @pytest.mark.asyncio
    async def test_process_memory_event_s3_vectors_failure_with_status(self, event):
        mock_memory = MagicMock()
        mock_memory.processing_status = "uploaded"
        mock_memory.processing_stage = "uploaded"

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=False):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=mock_memory):
                                    with pytest.raises(ProcessingError):
                                        await process_memory_event(event)


class TestDuplicateMemoryIdProcessing:
    @pytest.mark.asyncio
    async def test_duplicate_memory_id_idempotent(self):
        event = S3EventRecord(
            message_id="msg-1",
            bucket="test-bucket",
            key="memories/mem_abc123/original.jpg",
            event_name="ObjectCreated:Put",
            memory_id="mem_abc123",
            event_time="2024-01-15T10:30:00Z",
        )

        # First call: memory is uploaded
        mock_memory_1 = MagicMock()
        mock_memory_1.processing_status = "uploaded"
        mock_memory_1.processing_stage = "uploaded"

        # Second call: memory is already ready (idempotent)
        mock_memory_2 = MagicMock()
        mock_memory_2.processing_status = "ready"
        mock_memory_2.processing_stage = "ready"

        call_count = [0]

        def get_memory_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_memory_1
            return mock_memory_2

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=True):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, side_effect=get_memory_side_effect):
                                    result1 = await process_memory_event(event)
                                    result2 = await process_memory_event(event)
                                    assert result1 is True
                                    assert result2 is True


class TestStageTransitionValidator:
    """Tests for the stage transition validation logic."""

    def test_normal_forward_transition(self):
        """Test that normal forward transitions are allowed."""
        assert validate_stage_transition("ocr", "embedding") is True
        assert validate_stage_transition("embedding", "indexing") is True
        assert validate_stage_transition("indexing", "ready") is True
        assert validate_stage_transition(None, "ocr") is True

    def test_backward_transition_blocked(self):
        """Test that backward transitions are blocked."""
        assert validate_stage_transition("embedding", "ocr") is False
        assert validate_stage_transition("indexing", "embedding") is False
        assert validate_stage_transition("ready", "indexing") is False

    def test_same_stage_allowed(self):
        """Test that same-stage transitions are allowed (idempotent)."""
        assert validate_stage_transition("ocr", "ocr") is True
        assert validate_stage_transition("embedding", "embedding") is True

    def test_recovery_mode_allows_reset_to_ocr(self):
        """Test that recovery mode allows resetting to ocr from any stage."""
        assert validate_stage_transition("embedding", "ocr", allow_recovery=True) is True
        assert validate_stage_transition("indexing", "ocr", allow_recovery=True) is True
        assert validate_stage_transition("ready", "ocr", allow_recovery=True) is True

    def test_recovery_mode_still_blocks_other_backward(self):
        """Test that recovery mode doesn't allow arbitrary backward transitions."""
        assert validate_stage_transition("indexing", "embedding", allow_recovery=True) is False
        assert validate_stage_transition("ready", "embedding", allow_recovery=True) is False


class TestWorkerRecovery:
    """Tests for worker crash recovery logic."""

    @pytest.fixture
    def event(self):
        return S3EventRecord(
            message_id="msg-recovery",
            bucket="test-bucket",
            key="memories/mem_recovery/original.jpg",
            event_name="ObjectCreated:Put",
            memory_id="mem_recovery",
            event_time="2024-01-15T10:30:00Z",
        )

    @pytest.fixture
    def recent_processing_memory(self):
        """Memory that was recently updated (within stale threshold)."""
        mock = MagicMock()
        mock.processing_status = "processing"
        mock.processing_stage = "embedding"
        mock.updated_at = datetime.now(timezone.utc) - timedelta(seconds=60)  # 1 minute ago
        return mock

    @pytest.fixture
    def stale_processing_memory(self):
        """Memory that is stale (beyond stale threshold)."""
        mock = MagicMock()
        mock.processing_status = "processing"
        mock.processing_stage = "indexing"
        mock.updated_at = datetime.now(timezone.utc) - timedelta(seconds=900)  # 15 minutes ago
        return mock

    @pytest.fixture
    def no_timestamp_memory(self):
        """Memory with no updated_at timestamp."""
        mock = MagicMock()
        mock.processing_status = "processing"
        mock.processing_stage = "ocr"
        mock.updated_at = None
        return mock

    @pytest.fixture
    def failed_memory(self):
        """Memory that previously failed."""
        mock = MagicMock()
        mock.processing_status = "failed"
        mock.processing_stage = "failed"
        mock.updated_at = datetime.now(timezone.utc) - timedelta(seconds=300)
        return mock

    @pytest.mark.asyncio
    async def test_recently_updated_processing_skipped(self, event, recent_processing_memory):
        """TEST A: processing memory updated recently + duplicate SQS event -> skip duplicate."""
        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=True):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=recent_processing_memory):
                                    # Should skip because it was recently updated
                                    result = await process_memory_event(event)
                                    assert result is True

    @pytest.mark.asyncio
    async def test_stale_processing_recovery(self, event, stale_processing_memory):
        """TEST B: processing memory stale + SQS redelivery -> recover/reprocess."""
        mock_download = AsyncMock(return_value=b"fake_image_bytes")
        mock_extract = MagicMock(return_value="AWS Invoice")
        mock_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_upsert = AsyncMock(return_value=True)
        mock_ocr = AsyncMock(return_value=True)
        mock_status = AsyncMock(return_value=True)

        with patch("app.workers.processor.download_image_from_s3", mock_download):
            with patch.object(textract_service, "extract_text", mock_extract):
                with patch.object(voyage_embedding_service, "get_image_embedding", mock_embedding):
                    with patch.object(s3_vectors_service, "upsert_vector", mock_upsert):
                        with patch.object(database_service, "update_ocr_text", mock_ocr):
                            with patch.object(database_service, "update_memory_status", mock_status):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=stale_processing_memory):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    # Should proceed with full processing (ocr -> embedding -> indexing -> ready)
                                    mock_extract.assert_called_once()
                                    mock_embedding.assert_called_once()
                                    mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_timestamp_allows_recovery(self, event, no_timestamp_memory):
        """TEST C: worker crashes after setting processing but before OCR -> redelivery recovers."""
        mock_download = AsyncMock(return_value=b"fake_image_bytes")
        mock_extract = MagicMock(return_value="AWS Invoice")
        mock_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_upsert = AsyncMock(return_value=True)
        mock_ocr = AsyncMock(return_value=True)
        mock_status = AsyncMock(return_value=True)

        with patch("app.workers.processor.download_image_from_s3", mock_download):
            with patch.object(textract_service, "extract_text", mock_extract):
                with patch.object(voyage_embedding_service, "get_image_embedding", mock_embedding):
                    with patch.object(s3_vectors_service, "upsert_vector", mock_upsert):
                        with patch.object(database_service, "update_ocr_text", mock_ocr):
                            with patch.object(database_service, "update_memory_status", mock_status):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=no_timestamp_memory):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    mock_extract.assert_called_once()
                                    mock_embedding.assert_called_once()
                                    mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_crash_after_ocr_before_embedding_recovery(self, event):
        """TEST D: worker crashes after OCR but before embedding -> redelivery recovers safely."""
        # Memory stuck in embedding stage, stale
        stale_memory = MagicMock()
        stale_memory.processing_status = "processing"
        stale_memory.processing_stage = "embedding"
        stale_memory.updated_at = datetime.now(timezone.utc) - timedelta(seconds=900)

        mock_download = AsyncMock(return_value=b"fake_image_bytes")
        mock_extract = MagicMock(return_value="AWS Invoice")
        mock_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_upsert = AsyncMock(return_value=True)
        mock_ocr = AsyncMock(return_value=True)
        mock_status = AsyncMock(return_value=True)

        with patch("app.workers.processor.download_image_from_s3", mock_download):
            with patch.object(textract_service, "extract_text", mock_extract):
                with patch.object(voyage_embedding_service, "get_image_embedding", mock_embedding):
                    with patch.object(s3_vectors_service, "upsert_vector", mock_upsert):
                        with patch.object(database_service, "update_ocr_text", mock_ocr):
                            with patch.object(database_service, "update_memory_status", mock_status):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=stale_memory):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    # Should redo OCR, embedding, indexing
                                    mock_extract.assert_called_once()
                                    mock_embedding.assert_called_once()
                                    mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_crash_after_embedding_before_indexing_recovery(self, event):
        """TEST E: worker crashes after embedding but before indexing -> redelivery recovers safely."""
        stale_memory = MagicMock()
        stale_memory.processing_status = "processing"
        stale_memory.processing_stage = "indexing"
        stale_memory.updated_at = datetime.now(timezone.utc) - timedelta(seconds=900)

        mock_download = AsyncMock(return_value=b"fake_image_bytes")
        mock_extract = MagicMock(return_value="AWS Invoice")
        mock_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_upsert = AsyncMock(return_value=True)
        mock_ocr = AsyncMock(return_value=True)
        mock_status = AsyncMock(return_value=True)

        with patch("app.workers.processor.download_image_from_s3", mock_download):
            with patch.object(textract_service, "extract_text", mock_extract):
                with patch.object(voyage_embedding_service, "get_image_embedding", mock_embedding):
                    with patch.object(s3_vectors_service, "upsert_vector", mock_upsert):
                        with patch.object(database_service, "update_ocr_text", mock_ocr):
                            with patch.object(database_service, "update_memory_status", mock_status):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=stale_memory):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    mock_extract.assert_called_once()
                                    mock_embedding.assert_called_once()
                                    mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_ready_memory_skipped(self, event):
        """TEST F: already ready memory + duplicate SQS event -> skip."""
        ready_memory = MagicMock()
        ready_memory.processing_status = "ready"
        ready_memory.processing_stage = "ready"
        ready_memory.updated_at = datetime.now(timezone.utc)

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=True):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=ready_memory):
                                    result = await process_memory_event(event)
                                    assert result is True

    @pytest.mark.asyncio
    async def test_failed_memory_retried(self, event, failed_memory):
        """Failed memory can be retried."""
        mock_download = AsyncMock(return_value=b"fake_image_bytes")
        mock_extract = MagicMock(return_value="AWS Invoice")
        mock_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_upsert = AsyncMock(return_value=True)
        mock_ocr = AsyncMock(return_value=True)
        mock_status = AsyncMock(return_value=True)

        with patch("app.workers.processor.download_image_from_s3", mock_download):
            with patch.object(textract_service, "extract_text", mock_extract):
                with patch.object(voyage_embedding_service, "get_image_embedding", mock_embedding):
                    with patch.object(s3_vectors_service, "upsert_vector", mock_upsert):
                        with patch.object(database_service, "update_ocr_text", mock_ocr):
                            with patch.object(database_service, "update_memory_status", mock_status):
                                with patch.object(database_service, "get_memory", new_callable=AsyncMock, return_value=failed_memory):
                                    result = await process_memory_event(event)
                                    assert result is True
                                    mock_extract.assert_called_once()
                                    mock_embedding.assert_called_once()
                                    mock_upsert.assert_called_once()
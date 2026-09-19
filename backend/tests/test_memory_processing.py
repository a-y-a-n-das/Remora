import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError
from app.services.textract import TextractService, textract_service
from app.services.voyage import VoyageEmbeddingService, voyage_embedding_service
from app.services.s3_vectors import S3VectorsService, s3_vectors_service
from app.services.database import database_service
from app.workers.processor import ProcessingError, process_memory_event
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
        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=True) as mock_s3v:
                        with patch.object(database_service, "update_ocr_text", return_value=True) as mock_ocr:
                            result = await process_memory_event(event)
                            assert result is True
                            mock_ocr.assert_awaited_once()
                            mock_s3v.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_memory_event_download_failure(self, event):
        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = None

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                    with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                        with pytest.raises(ProcessingError):
                            await process_memory_event(event)

    @pytest.mark.asyncio
    async def test_process_memory_event_s3_vectors_failure(self, event):
        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=False):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
                                with pytest.raises(ProcessingError):
                                    await process_memory_event(event)

    @pytest.mark.asyncio
    async def test_process_memory_event_s3_vectors_failure_with_status(self, event):
        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", new_callable=AsyncMock, return_value=False):
                        with patch.object(database_service, "update_ocr_text", new_callable=AsyncMock, return_value=True):
                            with patch.object(database_service, "update_memory_status", new_callable=AsyncMock, return_value=True):
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

        with patch("app.workers.processor.download_image_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"fake_image_bytes"

            with patch.object(textract_service, "extract_text", return_value="AWS Invoice"):
                with patch.object(voyage_embedding_service, "get_image_embedding", return_value=[0.1] * 1024):
                    with patch.object(s3_vectors_service, "upsert_vector", return_value=True):
                        with patch.object(database_service, "update_ocr_text", return_value=True):
                            with patch.object(database_service, "update_memory_status", return_value=True):
                                result1 = await process_memory_event(event)
                                result2 = await process_memory_event(event)
                                assert result1 is True
                                assert result2 is True
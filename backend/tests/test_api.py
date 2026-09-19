import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Memory
from app.core.database import init_database, close_database, engine, async_session_maker


@pytest.fixture
def client():
    return TestClient(app)


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
    # Make the session itself an async context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def mock_session_maker(mock_db_session):
    """Create a mock session maker that returns our mock session as an async context manager."""
    # The session maker should be a callable that returns an async context manager
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


@pytest.fixture
def mock_settings():
    with patch("app.core.config.get_settings") as mock:
        mock.return_value = MagicMock(
            MAX_FILE_SIZE_MB=10,
            MAX_FILES_PER_REQUEST=5,
            RATE_LIMIT_UPLOADS=20,
            ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
            S3_BUCKET="test-bucket",
            PRESIGNED_URL_EXPIRY_SECONDS=3600,
            NEON_DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        )
        yield mock


def test_health_endpoint(client):
    with patch("app.api.health.get_s3_client") as mock_s3:
        mock_s3.return_value.head_bucket = MagicMock()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "checks" in data
        assert data["version"] == "0.1.0"


def test_readiness_endpoint(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_upload_init_success(client, mock_db_session, mock_settings):
    with patch("app.api.memories.generate_presigned_upload_url", new_callable=AsyncMock) as mock_presigned:
        mock_presigned.return_value = ("https://presigned.example.com/upload", "memories/mem_abc123/original.jpg", 3600)
        response = client.post("/memories/upload", json={
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 1024 * 1024,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["memory_id"].startswith("mem_")
        assert data["upload_url"] == "https://presigned.example.com/upload"
        # s3_key is the mock's return value
        assert data["s3_key"] == "memories/mem_abc123/original.jpg"
        assert data["expires_in"] == 3600
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_awaited_once()


def test_upload_init_invalid_mime_type(client, mock_db_session, mock_settings):
    response = client.post("/memories/upload", json={
        "filename": "test.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1024,
    })
    assert response.status_code == 400
    assert "MIME type not allowed" in response.json()["error"]


def test_upload_init_file_too_large(client, mock_db_session):
    with patch("app.api.memories.generate_presigned_upload_url", new_callable=AsyncMock) as mock_presigned:
        mock_presigned.return_value = ("https://presigned.example.com/upload", "memories/mem_abc123/original.jpg", 3600)
        with patch("app.services.storage.get_settings") as mock_storage_settings:
            mock_settings_obj = MagicMock()
            mock_settings_obj.MAX_FILE_SIZE_MB = 1
            mock_settings_obj.max_file_size_bytes = 1 * 1024 * 1024
            mock_settings_obj.MAX_FILES_PER_REQUEST = 5
            mock_settings_obj.RATE_LIMIT_UPLOADS = 20
            mock_settings_obj.ALLOWED_MIME_TYPES = ["image/jpeg", "image/png"]
            mock_settings_obj.S3_BUCKET = "test-bucket"
            mock_settings_obj.PRESIGNED_URL_EXPIRY_SECONDS = 3600
            mock_storage_settings.return_value = mock_settings_obj
            response = client.post("/memories/upload", json={
                "filename": "test.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 2 * 1024 * 1024,
            })
    assert response.status_code == 400
    assert "File too large" in response.json()["error"]


def test_upload_init_missing_fields(client):
    response = client.post("/memories/upload", json={})
    assert response.status_code == 422


def test_get_memory_status_found(client, mock_db_session):
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_test123"
    mock_memory.processing_status = "uploaded"
    mock_memory.moderation_status = "pending"
    mock_memory.original_filename = "test.jpg"
    mock_memory.mime_type = "image/jpeg"
    mock_memory.size_bytes = 1024
    mock_memory.created_at = "2024-01-15T10:30:00Z"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_test123/status")
    assert response.status_code == 200
    data = response.json()
    assert data["memory_id"] == "mem_test123"
    assert data["processing_status"] == "uploaded"
    assert data["moderation_status"] == "pending"
    assert data["original_filename"] == "test.jpg"


def test_get_memory_status_not_found(client, mock_db_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_nonexistent/status")
    assert response.status_code == 404


def test_get_download_url_success(client, mock_db_session):
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_test123"
    mock_memory.s3_key = "memories/mem_test123/original.jpg"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.api.memories.generate_presigned_download_url", new_callable=AsyncMock) as mock_download:
        mock_download.return_value = "https://download.example.com"
        response = client.get("/memories/mem_test123/download-url")
        assert response.status_code == 200
        assert response.json()["download_url"] == "https://download.example.com"


def test_get_download_url_not_found(client, mock_db_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_nonexistent/download-url")
    assert response.status_code == 404


def test_get_download_url_no_s3_key(client, mock_db_session):
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_test123"
    mock_memory.s3_key = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_test123/download-url")
    assert response.status_code == 404


def test_upload_init_creates_memory_record(client, mock_db_session, mock_settings):
    """Test that upload initialization creates a Memory record in the database."""
    with patch("app.api.memories.generate_presigned_upload_url", new_callable=AsyncMock) as mock_presigned:
        mock_presigned.return_value = ("https://presigned.example.com/upload", "memories/mem_abc123/original.jpg", 3600)
        response = client.post("/memories/upload", json={
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 1024 * 1024,
        })
        assert response.status_code == 200

        # Verify Memory was created with correct fields
        mock_db_session.add.assert_called_once()
        added_memory = mock_db_session.add.call_args[0][0]
        assert isinstance(added_memory, Memory)
        assert added_memory.id.startswith("mem_")
        assert added_memory.original_filename == "test.jpg"
        assert added_memory.mime_type == "image/jpeg"
        assert added_memory.size_bytes == 1024 * 1024
        assert added_memory.processing_status == "uploaded"
        assert added_memory.moderation_status == "pending"
        # s3_key is the mock's return value
        assert added_memory.s3_key == "memories/mem_abc123/original.jpg"


def test_memory_status_read_from_database(client, mock_db_session):
    """Test that memory status can be read from the database."""
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_status123"
    mock_memory.processing_status = "processing"
    mock_memory.moderation_status = "pending"
    mock_memory.original_filename = "status_test.jpg"
    mock_memory.mime_type = "image/jpeg"
    mock_memory.size_bytes = 2048
    mock_memory.created_at = "2024-01-15T10:30:00Z"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_status123/status")
    assert response.status_code == 200
    data = response.json()
    assert data["memory_id"] == "mem_status123"
    assert data["processing_status"] == "processing"
    assert data["original_filename"] == "status_test.jpg"


def test_processing_status_updates_persist(client, mock_db_session):
    """Test that processing status updates persist to the database."""
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_update123"
    mock_memory.processing_status = "ready"
    mock_memory.moderation_status = "approved"
    mock_memory.original_filename = "update_test.jpg"
    mock_memory.mime_type = "image/png"
    mock_memory.size_bytes = 4096
    mock_memory.created_at = "2024-01-15T10:30:00Z"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_memory
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_update123/status")
    assert response.status_code == 200
    data = response.json()
    assert data["processing_status"] == "ready"
    assert data["moderation_status"] == "approved"
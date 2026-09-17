import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_s3_client():
    with patch("app.api.memories.get_async_s3_client") as mock:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.generate_presigned_url = AsyncMock(return_value="https://presigned.example.com/upload")
        mock.return_value = mock_client
        yield mock_client


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


def test_upload_init_success(client, mock_s3_client):
    with patch("app.api.memories.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            MAX_FILE_SIZE_MB=10,
            MAX_FILES_PER_REQUEST=5,
            RATE_LIMIT_UPLOADS=20,
            ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
            S3_BUCKET="test-bucket",
            PRESIGNED_URL_EXPIRY_SECONDS=3600,
        )
        response = client.post("/api/memories/upload", json={
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 1024 * 1024,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["memory_id"].startswith("mem_")
        assert data["upload_url"] == "https://presigned.example.com/upload"
        assert data["s3_key"] == "memories/" + data["memory_id"] + "/original.jpg"
        assert data["expires_in"] == 3600


def test_upload_init_invalid_mime_type(client):
    with patch("app.api.memories.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
            MAX_FILE_SIZE_MB=10,
            RATE_LIMIT_UPLOADS=20,
        )
        response = client.post("/api/memories/upload", json={
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
        })
        assert response.status_code == 400
        assert "MIME type not allowed" in response.json()["error"]


def test_upload_init_file_too_large(client):
    with patch("app.api.memories.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            ALLOWED_MIME_TYPES=["image/jpeg"],
            MAX_FILE_SIZE_MB=1,
            RATE_LIMIT_UPLOADS=20,
        )
        response = client.post("/api/memories/upload", json={
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 2 * 1024 * 1024,
        })
        assert response.status_code == 400
        assert "File too large" in response.json()["error"]


def test_upload_init_missing_fields(client):
    response = client.post("/api/memories/upload", json={})
    assert response.status_code == 422


def test_get_memory_status_found(client):
    from app.api.memories import _memory_status_store
    _memory_status_store.clear()
    mem_id = "mem_test123"
    _memory_status_store[mem_id] = {
        "memory_id": mem_id,
        "processing_status": "uploaded",
        "moderation_status": "pending",
        "original_filename": "test.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
        "s3_key": "memories/mem_test123/original.jpg",
        "uploaded_at": "now",
        "error_message": None,
    }

    response = client.get(f"/api/memories/{mem_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["memory_id"] == mem_id
    assert data["processing_status"] == "uploaded"
    assert data["moderation_status"] == "pending"
    assert data["original_filename"] == "test.jpg"


def test_get_memory_status_not_found(client):
    response = client.get("/api/memories/mem_nonexistent/status")
    assert response.status_code == 404


def test_get_download_url_success(client, mock_s3_client):
    from app.api.memories import _memory_status_store
    _memory_status_store.clear()
    mem_id = "mem_test123"
    _memory_status_store[mem_id] = {
        "memory_id": mem_id,
        "processing_status": "uploaded",
        "moderation_status": "pending",
        "original_filename": "test.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
        "s3_key": "memories/mem_test123/original.jpg",
        "uploaded_at": "now",
        "error_message": None,
    }

    mock_s3_client.generate_presigned_url = AsyncMock(return_value="https://download.example.com")

    response = client.get(f"/api/memories/{mem_id}/download-url")
    assert response.status_code == 200
    assert response.json()["download_url"] == "https://download.example.com"


def test_get_download_url_not_found(client):
    response = client.get("/api/memories/mem_nonexistent/download-url")
    assert response.status_code == 404


def test_get_download_url_no_s3_key(client):
    from app.api.memories import _memory_status_store
    _memory_status_store.clear()
    mem_id = "mem_test123"
    _memory_status_store[mem_id] = {
        "memory_id": mem_id,
        "processing_status": "uploaded",
        "moderation_status": "pending",
        "original_filename": "test.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
        "s3_key": None,
        "uploaded_at": "now",
        "error_message": None,
    }

    response = client.get(f"/api/memories/{mem_id}/download-url")
    assert response.status_code == 404
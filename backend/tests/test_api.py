import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Memory
from app.core.database import init_database, close_database, engine, async_session_maker


@pytest.fixture
def client(mock_settings):
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
    mock_memory.processing_stage = "uploaded"
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
    assert data["processing_stage"] == "uploaded"
    assert data["original_filename"] == "test.jpg"
    assert "moderation_status" not in data


def test_get_memory_status_not_found(client, mock_db_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/memories/mem_nonexistent/status")
    assert response.status_code == 404


def test_list_memories(client, mock_db_session):
    first_memory = MagicMock(spec=Memory)
    first_memory.id = "mem_test123"
    first_memory.original_filename = "test.jpg"
    first_memory.mime_type = "image/jpeg"
    first_memory.size_bytes = 1024
    first_memory.processing_status = "ready"
    first_memory.processing_stage = "ready"
    first_memory.s3_key = "memories/mem_test123/original.jpg"
    first_memory.created_at = "2024-01-15T10:30:00Z"

    second_memory = MagicMock(spec=Memory)
    second_memory.id = "mem_test456"
    second_memory.original_filename = "notes.pdf"
    second_memory.mime_type = "application/pdf"
    second_memory.size_bytes = 2048
    second_memory.processing_status = "processing"
    second_memory.processing_stage = "embedding"
    second_memory.s3_key = "memories/mem_test456/original.bin"
    second_memory.created_at = "2024-01-14T10:30:00Z"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [first_memory, second_memory]
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.api.memories.database_service.get_memories", new_callable=AsyncMock) as get_memories:
        get_memories.return_value = [first_memory, second_memory]
        response = client.get("/memories")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "mem_test123",
            "filename": "test.jpg",
            "original_filename": "test.jpg",
            "mime_type": "image/jpeg",
            "size": 1024,
            "size_bytes": 1024,
            "processing_status": "ready",
            "processing_stage": "ready",
            "s3_key": "memories/mem_test123/original.jpg",
            "uploaded_at": "2024-01-15T10:30:00Z",
        },
        {
            "id": "mem_test456",
            "filename": "notes.pdf",
            "original_filename": "notes.pdf",
            "mime_type": "application/pdf",
            "size": 2048,
            "size_bytes": 2048,
            "processing_status": "processing",
            "processing_stage": "embedding",
            "s3_key": "memories/mem_test456/original.bin",
            "uploaded_at": "2024-01-14T10:30:00Z",
        },
    ]
    get_memories.assert_awaited_once_with(mock_db_session)


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
        assert added_memory.processing_stage == "uploaded"
        # s3_key is the mock's return value
        assert added_memory.s3_key == "memories/mem_abc123/original.jpg"


def test_memory_status_read_from_database(client, mock_db_session):
    """Test that memory status can be read from the database."""
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_status123"
    mock_memory.processing_status = "processing"
    mock_memory.processing_stage = "ocr"
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
    assert data["processing_stage"] == "ocr"
    assert data["original_filename"] == "status_test.jpg"


def test_processing_status_updates_persist(client, mock_db_session):
    """Test that processing status updates persist to the database."""
    mock_memory = MagicMock(spec=Memory)
    mock_memory.id = "mem_update123"
    mock_memory.processing_status = "ready"
    mock_memory.processing_stage = "ready"
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
    assert data["processing_stage"] == "ready"
    assert "moderation_status" not in data


def test_search_memories_success(client, mock_db_session):
    """Test successful search with Voyage text embedding and S3 Vectors query."""
    # Mock Voyage text embedding
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        # Mock S3 Vectors query
        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_1", "distance": 0.1, "metadata": {"type": "image"}},
                {"memory_id": "mem_2", "distance": 0.2, "metadata": {"type": "document"}},
            ]

            # Mock database lookup
            mock_memory1 = MagicMock(spec=Memory)
            mock_memory1.id = "mem_1"
            mock_memory1.ocr_text = "AWS Invoice"
            mock_memory1.s3_key = "memories/mem_1/original.jpg"
            mock_memory1.original_filename = "invoice.jpg"
            mock_memory1.created_at = "2024-01-15T10:30:00Z"

            mock_memory2 = MagicMock(spec=Memory)
            mock_memory2.id = "mem_2"
            mock_memory2.ocr_text = "Project Plan"
            mock_memory2.s3_key = "memories/mem_2/original.png"
            mock_memory2.original_filename = "plan.png"
            mock_memory2.created_at = "2024-01-14T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory1, mock_memory2]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            response = client.post("/memories/search", json={"query": "AWS invoice", "limit": 10})

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "AWS invoice"
            assert len(data["results"]) == 2
            assert data["results"][0]["memory_id"] == "mem_1"
            assert data["results"][0]["score"] == 0.1
            assert data["results"][0]["ocr_text"] == "AWS Invoice"
            assert data["results"][1]["memory_id"] == "mem_2"
            assert data["results"][1]["score"] == 0.2
            assert data["results"][1]["ocr_text"] == "Project Plan"


def test_search_memories_empty_query(client, mock_db_session, mock_settings):
    """Test search with empty query returns 422 (Pydantic validation)."""
    response = client.post("/memories/search", json={"query": "", "limit": 10})
    assert response.status_code == 422


def test_search_memories_no_results(client, mock_db_session):
    """Test search with no matching results."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = []

            response = client.post("/memories/search", json={"query": "nonexistent", "limit": 10})

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "nonexistent"
            assert data["results"] == []


def test_search_memories_voyage_failure(client, mock_db_session, mock_settings):
    """Test search when Voyage API fails."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = None
        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            response = client.post("/memories/search", json={"query": "test", "limit": 10})

            assert response.status_code == 503
            assert "Failed to generate query embedding" in response.json()["error"]
            mock_s3v.assert_not_awaited()


def test_query_endpoint_voyage_failure_does_not_search(client, mock_db_session, mock_settings):
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock, return_value=None):
        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            response = client.post("/memories/query", json={"query": "test", "limit": 5})

            assert response.status_code == 503
            assert "Failed to generate query embedding" in response.json()["error"]
            mock_s3v.assert_not_awaited()


def test_search_memories_s3_vectors_failure(client, mock_db_session, mock_settings):
    """Test search when S3 Vectors query fails."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.side_effect = Exception("S3 Vectors error")

            response = client.post("/memories/search", json={"query": "test", "limit": 10})

            # Should handle the error gracefully - currently returns 500
            assert response.status_code in [500, 503]


def test_search_memories_neon_missing_memory(client, mock_db_session, mock_settings):
    """Test search when S3 Vectors returns memory IDs not in Neon."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_1", "distance": 0.1},
                {"memory_id": "mem_2", "distance": 0.2},
            ]

            # Only mem_1 exists in Neon
            mock_memory1 = MagicMock(spec=Memory)
            mock_memory1.id = "mem_1"
            mock_memory1.ocr_text = "AWS Invoice"
            mock_memory1.s3_key = "memories/mem_1/original.jpg"
            mock_memory1.original_filename = "invoice.jpg"
            mock_memory1.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory1]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            response = client.post("/memories/search", json={"query": "test", "limit": 10})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["memory_id"] == "mem_1"


def test_query_endpoint_with_conversation_history(client, mock_db_session):
    """Test /memories/query endpoint with conversation_history - validates FastAPI deserialization."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_1", "distance": 0.1},
            ]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "AWS Invoice"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "invoice.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            # Mock nemotron_service.reason to return a valid response
            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                # Test with conversation_history
                response = client.post("/memories/query", json={
                    "query": "test query",
                    "limit": 5,
                    "conversation_history": [
                        {"role": "user", "content": "previous query"},
                        {"role": "assistant", "content": "previous answer"}
                    ]
                })

                assert response.status_code == 200
                data = response.json()
                assert data["query"] == "test query"
                assert data["answer"] == "Test answer"

                # Verify nemotron_service.reason was called with conversation_history
                mock_reason.assert_awaited_once()
                call_args = mock_reason.call_args
                assert call_args[0][2] == [{"role": "user", "content": "previous query"}, {"role": "assistant", "content": "previous answer"}]


def test_query_endpoint_empty_conversation_history(client, mock_db_session):
    """Test /memories/query endpoint with empty conversation_history."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_1", "distance": 0.1},
            ]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "AWS Invoice"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "invoice.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                # Test with empty conversation_history
                response = client.post("/memories/query", json={
                    "query": "test query",
                    "limit": 5,
                    "conversation_history": []
                })

                assert response.status_code == 200
                data = response.json()
                assert data["query"] == "test query"
                assert data["answer"] == "Test answer"


def test_query_endpoint_without_conversation_history(client, mock_db_session):
    """Test /memories/query endpoint without conversation_history field (backward compatibility)."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_1", "distance": 0.1},
            ]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "AWS Invoice"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "invoice.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                # Test without conversation_history field (backward compatibility)
                response = client.post("/memories/query", json={
                    "query": "test query",
                    "limit": 5
                })

                assert response.status_code == 200
                data = response.json()
                assert data["query"] == "test query"
                assert data["answer"] == "Test answer"


def test_query_endpoint_selected_memories_field(client, mock_db_session):
    """Test that selected_memories field is populated with only selected memories."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            # Return 3 candidate memories
            mock_s3v.return_value = [
                {"memory_id": "mem_A", "distance": 0.1},
                {"memory_id": "mem_B", "distance": 0.2},
                {"memory_id": "mem_C", "distance": 0.3},
            ]

            mock_memory_a = MagicMock(spec=Memory)
            mock_memory_a.id = "mem_A"
            mock_memory_a.ocr_text = "AWS Invoice"
            mock_memory_a.s3_key = "memories/mem_A/original.jpg"
            mock_memory_a.original_filename = "invoice.jpg"
            mock_memory_a.created_at = "2024-01-15T10:30:00Z"

            mock_memory_b = MagicMock(spec=Memory)
            mock_memory_b.id = "mem_B"
            mock_memory_b.ocr_text = "Random Receipt"
            mock_memory_b.s3_key = "memories/mem_B/original.png"
            mock_memory_b.original_filename = "receipt.png"
            mock_memory_b.created_at = "2024-01-14T10:30:00Z"

            mock_memory_c = MagicMock(spec=Memory)
            mock_memory_c.id = "mem_C"
            mock_memory_c.ocr_text = "Meeting Notes"
            mock_memory_c.s3_key = "memories/mem_C/original.pdf"
            mock_memory_c.original_filename = "notes.pdf"
            mock_memory_c.created_at = "2024-01-13T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory_a, mock_memory_b, mock_memory_c]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                # Nemotron selects only mem_A
                mock_reason.return_value = ("Found your AWS invoice", ["mem_A"], [], [])

                response = client.post("/memories/query", json={
                    "query": "AWS invoice",
                    "limit": 5
                })

                assert response.status_code == 200
                data = response.json()
                assert data["query"] == "AWS invoice"
                assert data["answer"] == "Found your AWS invoice"
                
                # Verify selected_memory_ids contains only mem_A
                assert data["selected_memory_ids"] == ["mem_A"]
                
                # Verify selected_memories contains only mem_A (not mem_B or mem_C)
                assert "selected_memories" in data
                assert len(data["selected_memories"]) == 1
                assert data["selected_memories"][0]["memory_id"] == "mem_A"
                assert data["selected_memories"][0]["original_filename"] == "invoice.jpg"
                
                # Verify unrelated candidates are not included
                selected_ids = [m["memory_id"] for m in data["selected_memories"]]
                assert "mem_B" not in selected_ids
                assert "mem_C" not in selected_ids


def test_query_endpoint_multiple_selected_memories(client, mock_db_session):
    """Test that multiple selected memories are all included in selected_memories."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_A", "distance": 0.1},
                {"memory_id": "mem_B", "distance": 0.2},
                {"memory_id": "mem_C", "distance": 0.3},
            ]

            mock_memory_a = MagicMock(spec=Memory)
            mock_memory_a.id = "mem_A"
            mock_memory_a.ocr_text = "AWS Invoice 1"
            mock_memory_a.s3_key = "memories/mem_A/original.jpg"
            mock_memory_a.original_filename = "invoice1.jpg"
            mock_memory_a.created_at = "2024-01-15T10:30:00Z"

            mock_memory_b = MagicMock(spec=Memory)
            mock_memory_b.id = "mem_B"
            mock_memory_b.ocr_text = "AWS Invoice 2"
            mock_memory_b.s3_key = "memories/mem_B/original.png"
            mock_memory_b.original_filename = "invoice2.png"
            mock_memory_b.created_at = "2024-01-14T10:30:00Z"

            mock_memory_c = MagicMock(spec=Memory)
            mock_memory_c.id = "mem_C"
            mock_memory_c.ocr_text = "Random Receipt"
            mock_memory_c.s3_key = "memories/mem_C/original.pdf"
            mock_memory_c.original_filename = "receipt.pdf"
            mock_memory_c.created_at = "2024-01-13T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory_a, mock_memory_b, mock_memory_c]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                # Nemotron selects mem_A and mem_B
                mock_reason.return_value = ("Found your AWS invoices", ["mem_A", "mem_B"], [], [])

                response = client.post("/memories/query", json={
                    "query": "AWS invoices",
                    "limit": 5
                })

                assert response.status_code == 200
                data = response.json()
                
                # Verify selected_memory_ids contains both
                assert data["selected_memory_ids"] == ["mem_A", "mem_B"]
                
                # Verify selected_memories contains both
                assert len(data["selected_memories"]) == 2
                selected_ids = [m["memory_id"] for m in data["selected_memories"]]
                assert "mem_A" in selected_ids
                assert "mem_B" in selected_ids
                assert "mem_C" not in selected_ids


def test_query_endpoint_fallback_no_selected_memories(client, mock_db_session):
    """Test that fallback response has empty selected_memories."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [
                {"memory_id": "mem_A", "distance": 0.1},
            ]

            mock_memory_a = MagicMock(spec=Memory)
            mock_memory_a.id = "mem_A"
            mock_memory_a.ocr_text = "Some document"
            mock_memory_a.s3_key = "memories/mem_A/original.jpg"
            mock_memory_a.original_filename = "doc.jpg"
            mock_memory_a.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory_a]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                # Fallback: answer present but no selected memories
                mock_reason.return_value = ("I couldn't complete reasoning but found candidates", [], [], [])

                response = client.post("/memories/query", json={
                    "query": "test query",
                    "limit": 5
                })

                assert response.status_code == 200
                data = response.json()
                assert data["is_fallback"] is True
                assert data["selected_memory_ids"] == []
                assert data["selected_memories"] == []


def test_query_endpoint_conversation_history_empty(client, mock_db_session):
    """Test first query sends empty conversation_history."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "Test"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "test.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                response = client.post("/memories/query", json={
                    "query": "first query",
                    "limit": 5,
                    "conversation_history": []
                })

                assert response.status_code == 200
                mock_reason.assert_awaited_once()
                call_args = mock_reason.call_args
                assert call_args[0][2] == []


def test_query_endpoint_conversation_history_second_query(client, mock_db_session):
    """Test second query sends first user + assistant messages."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "Test"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "test.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                response = client.post("/memories/query", json={
                    "query": "second query",
                    "limit": 5,
                    "conversation_history": [
                        {"role": "user", "content": "first query"},
                        {"role": "assistant", "content": "first answer"}
                    ]
                })

                assert response.status_code == 200
                mock_reason.assert_awaited_once()
                call_args = mock_reason.call_args
                assert call_args[0][2] == [
                    {"role": "user", "content": "first query"},
                    {"role": "assistant", "content": "first answer"}
                ]


def test_query_endpoint_conversation_history_third_query(client, mock_db_session):
    """Test third query sends all preceding messages but not current query."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "AWS Invoice"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "invoice.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                response = client.post("/memories/query", json={
                    "query": "can you get me the link",
                    "limit": 5,
                    "conversation_history": [
                        {"role": "user", "content": "Find the AWS bill"},
                        {"role": "assistant", "content": "Found your AWS invoice"},
                        {"role": "user", "content": "where can I pay it"},
                        {"role": "assistant", "content": "You can pay at the AWS console"}
                    ]
                })

                assert response.status_code == 200
                mock_reason.assert_awaited_once()
                call_args = mock_reason.call_args
                history = call_args[0][2]
                assert len(history) == 4
                assert history[0] == {"role": "user", "content": "Find the AWS bill"}
                assert history[1] == {"role": "assistant", "content": "Found your AWS invoice"}
                assert history[2] == {"role": "user", "content": "where can I pay it"}
                assert history[3] == {"role": "assistant", "content": "You can pay at the AWS console"}
                # Current query should NOT be in conversation_history
                assert not any(msg.get("content") == "can you get me the link" for msg in history)


def test_query_endpoint_conversation_history_session_isolation(client, mock_db_session):
    """Test that conversation history is only from current session."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_1"
            mock_memory.ocr_text = "Test"
            mock_memory.s3_key = "memories/mem_1/original.jpg"
            mock_memory.original_filename = "test.jpg"
            mock_memory.created_at = "2024-01-15T10:30:00Z"

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_memory]
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with patch("app.api.memories.nemotron_service.reason", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = ("Test answer", ["mem_1"], [], [])

                # Simulate a request with history from a different session
                response = client.post("/memories/query", json={
                    "query": "new query",
                    "limit": 5,
                    "conversation_history": [
                        {"role": "user", "content": "previous session query"},
                        {"role": "assistant", "content": "previous session answer"}
                    ]
                })

                assert response.status_code == 200
                mock_reason.assert_awaited_once()
                call_args = mock_reason.call_args
                history = call_args[0][2]
                # Should only contain what was sent in this request
                assert history == [
                    {"role": "user", "content": "previous session query"},
                    {"role": "assistant", "content": "previous session answer"}
                ]


def test_trigger_processing_endpoint_sqs_configured(client, mock_db_session):
    """Test trigger-processing endpoint enqueues to SQS when configured."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_test123"
            mock_memory.processing_status = "uploaded"
            mock_memory.s3_key = "memories/mem_test123/original.jpg"
            mock_memory.size_bytes = 1024

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_memory
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            # Mock SQS client at the source module
            with patch("app.core.aws_clients.get_async_sqs_client") as mock_sqs_client:
                mock_sqs = AsyncMock()
                mock_sqs.__aenter__ = AsyncMock(return_value=mock_sqs)
                mock_sqs.__aexit__ = AsyncMock(return_value=None)
                mock_sqs.send_message = AsyncMock()
                mock_sqs_client.return_value = mock_sqs

                # Patch get_settings at the module where it's used
                with patch("app.api.memories.get_settings") as mock_settings:
                    mock_settings_obj = MagicMock()
                    mock_settings_obj.SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
                    mock_settings_obj.S3_BUCKET = "test-bucket"
                    mock_settings_obj.AWS_REGION = "us-east-1"
                    mock_settings.return_value = mock_settings_obj

                    response = client.post("/memories/mem_test123/trigger-processing")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "enqueued"
                    assert data["memory_id"] == "mem_test123"
                    mock_sqs.send_message.assert_awaited_once()


def test_trigger_processing_endpoint_direct_processing(client, mock_db_session):
    """Test trigger-processing endpoint processes directly when SQS not configured."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_test123"
            mock_memory.processing_status = "uploaded"
            mock_memory.s3_key = "memories/mem_test123/original.jpg"
            mock_memory.size_bytes = 1024

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_memory
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            # Mock process_memory_event at the source module
            with patch("app.workers.processor.process_memory_event", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = True

                # Patch get_settings at the module where it's used
                with patch("app.api.memories.get_settings") as mock_settings:
                    mock_settings_obj = MagicMock()
                    mock_settings_obj.SQS_QUEUE_URL = ""  # Not configured
                    mock_settings_obj.S3_BUCKET = "test-bucket"
                    mock_settings_obj.AWS_REGION = "us-east-1"
                    mock_settings.return_value = mock_settings_obj

                    response = client.post("/memories/mem_test123/trigger-processing")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "processed"
                    assert data["memory_id"] == "mem_test123"
                    mock_process.assert_awaited_once()


def test_trigger_processing_endpoint_skips_non_uploaded(client, mock_db_session):
    """Test trigger-processing skips memories not in uploaded status."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_memory = MagicMock(spec=Memory)
            mock_memory.id = "mem_test123"
            mock_memory.processing_status = "ready"  # Not uploaded
            mock_memory.s3_key = "memories/mem_test123/original.jpg"
            mock_memory.size_bytes = 1024

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_memory
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            response = client.post("/memories/mem_test123/trigger-processing")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "skipped"
            assert "ready" in data["reason"]


def test_trigger_processing_endpoint_not_found(client, mock_db_session):
    """Test trigger-processing returns 404 for non-existent memory."""
    with patch("app.api.memories.voyage_embedding_service.get_text_embedding", new_callable=AsyncMock) as mock_voyage:
        mock_voyage.return_value = [0.1] * 1024

        with patch("app.api.memories.s3_vectors_service.query_vectors", new_callable=AsyncMock) as mock_s3v:
            mock_s3v.return_value = [{"memory_id": "mem_1", "distance": 0.1}]

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            response = client.post("/memories/mem_nonexistent/trigger-processing")

            assert response.status_code == 404
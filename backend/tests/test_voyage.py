import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.voyage import VoyageEmbeddingService


class TestVoyageEmbeddingService:
    @pytest.fixture
    def voyage_service(self):
        service = VoyageEmbeddingService()
        # Override settings for testing
        service.settings = MagicMock(
            VOYAGE_API_KEY="test-api-key",
            VOYAGE_MODEL="voyage-multimodal-3",
            VOYAGE_EMBEDDING_DIMENSION=1024,
            VOYAGE_MAX_RETRIES=3,
            VOYAGE_TIMEOUT_SECONDS=30.0,
        )
        return service

    @pytest.mark.asyncio
    async def test_successful_image_embedding(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1024}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes", "test text")

        assert embedding is not None
        assert len(embedding) == 1024
        assert all(v == 0.1 for v in embedding)

    @pytest.mark.asyncio
    async def test_successful_text_embedding(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.2] * 1024}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_text_embedding("search query")

        assert embedding is not None
        assert len(embedding) == 1024
        assert all(v == 0.2 for v in embedding)

    @pytest.mark.asyncio
    async def test_embedding_dimension_mismatch(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 512}]  # Wrong dimension
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_missing_api_key(self, voyage_service):
        voyage_service.settings.VOYAGE_API_KEY = ""
        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")
        assert embedding is None

    @pytest.mark.asyncio
    async def test_missing_model(self, voyage_service):
        voyage_service.settings.VOYAGE_MODEL = ""
        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")
        assert embedding is None

    @pytest.mark.asyncio
    async def test_http_error_response(self, voyage_service):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_timeout(self, voyage_service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_malformed_response_no_data(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_malformed_response_empty_data(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_malformed_response_missing_embedding(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": None}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None

    @pytest.mark.asyncio
    async def test_empty_text_embedding(self, voyage_service):
        embedding = await voyage_service.get_text_embedding("")
        assert embedding is None

        embedding = await voyage_service.get_text_embedding("   ")
        assert embedding is None

    @pytest.mark.asyncio
    async def test_text_embedding_dimension(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.3] * 1024}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_text_embedding("search query")

        assert embedding is not None
        assert len(embedding) == 1024

    @pytest.mark.asyncio
    async def test_text_embedding_dimension_mismatch(self, voyage_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.3] * 512}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        voyage_service.set_client(mock_client)

        embedding = await voyage_service.get_text_embedding("search query")

        assert embedding is None
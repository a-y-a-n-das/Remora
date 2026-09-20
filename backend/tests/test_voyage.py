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
    async def test_rate_limit_retries_and_honors_retry_after(self, voyage_service):
        rate_limited = httpx.Response(
            429,
            headers={"Retry-After": "7"},
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        success = httpx.Response(
            200,
            json={"data": [{"embedding": [0.1] * 1024}]},
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        mock_client = AsyncMock()
        mock_client.post.side_effect = [rate_limited, success]
        voyage_service.set_client(mock_client)

        with patch("app.services.voyage.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is not None
        assert mock_client.post.await_count == 2
        mock_sleep.assert_awaited_once_with(7.0)

    @pytest.mark.asyncio
    async def test_rate_limit_retries_are_bounded(self, voyage_service):
        response = httpx.Response(
            429,
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = response
        voyage_service.set_client(mock_client)

        with patch("app.services.voyage.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            embedding = await voyage_service.get_text_embedding("search query")

        assert embedding is None
        assert mock_client.post.await_count == voyage_service.settings.VOYAGE_MAX_RETRIES + 1
        assert mock_sleep.await_count == voyage_service.settings.VOYAGE_MAX_RETRIES

    @pytest.mark.asyncio
    async def test_server_error_and_timeout_retry(self, voyage_service):
        server_error = httpx.Response(
            503,
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        success = httpx.Response(
            200,
            json={"data": [{"embedding": [0.2] * 1024}]},
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        mock_client = AsyncMock()
        mock_client.post.side_effect = [server_error, httpx.TimeoutException("timed out"), success]
        voyage_service.set_client(mock_client)

        with patch("app.services.voyage.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            embedding = await voyage_service.get_text_embedding("search query")

        assert embedding is not None
        assert mock_client.post.await_count == 3
        assert mock_sleep.await_count == 2

    @pytest.mark.asyncio
    async def test_permanent_http_error_is_not_retried(self, voyage_service):
        response = httpx.Response(
            401,
            request=httpx.Request("POST", "https://api.voyageai.com/v1/multimodalembeddings"),
        )
        mock_client = AsyncMock()
        mock_client.post.return_value = response
        voyage_service.set_client(mock_client)

        with patch("app.services.voyage.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            embedding = await voyage_service.get_image_embedding(b"fake_image_bytes")

        assert embedding is None
        mock_client.post.assert_awaited_once()
        mock_sleep.assert_not_awaited()

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
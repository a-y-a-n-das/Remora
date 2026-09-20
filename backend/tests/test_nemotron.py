import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import json
from app.services.nemotron import NemotronService


class TestNemotronService:
    @pytest.fixture
    def nemotron_service(self):
        service = NemotronService()
        # Override settings for testing
        service.settings = MagicMock(
            NVIDIA_API_KEY="test-api-key",
            NVIDIA_API_BASE="https://integrate.api.nvidia.com/v1",
            NEMOTRON_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            NEMOTRON_MAX_RETRIES=3,
            NEMOTRON_TIMEOUT_SECONDS=60.0,
        )
        return service

    @pytest.fixture
    def mock_client(self):
        mock = AsyncMock()
        return mock

    @pytest.fixture(autouse=True)
    def setup_client(self, nemotron_service, mock_client):
        nemotron_service.set_client(mock_client)
        yield
        nemotron_service.set_client(None)

    @pytest.mark.asyncio
    async def test_reason_uses_configured_model(self, nemotron_service):
        """Test that the configured NEMOTRON_MODEL is passed to the API request."""
        # Mock response that looks like a final answer (no tool calls)
        mock_response = MagicMock()
        final_answer = json.dumps({
            "answer": "Test answer",
            "selected_memory_ids": ["mem_1"],
            "sources": [],
            "actions": []
        })
        mock_response.json.return_value = {
            "choices": [{"message": {"content": final_answer, "tool_calls": []}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        nemotron_service.set_client(mock_client)

        memories = [
            {
                "memory_id": "mem_1",
                "distance": 0.1,
                "ocr_text": "Test OCR",
                "s3_key": "memories/mem_1/original.jpg",
                "original_filename": "test.jpg",
            }
        ]

        # Mock S3 image fetch to avoid real S3 calls
        with patch("app.services.nemotron.get_async_s3_client") as mock_s3_client:
            mock_s3 = AsyncMock()
            mock_s3.get_object = AsyncMock(return_value={
                "Body": AsyncMock(read=AsyncMock(return_value=b"fake_image_bytes"))
            })
            mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
            mock_s3.__aexit__ = AsyncMock(return_value=None)
            mock_s3_client.return_value = mock_s3

            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")

                await nemotron_service.reason("test query", [memories[0]])

        # Verify the model passed to the API matches the configured model
        mock_client.post.assert_awaited()
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["model"] == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

    @pytest.mark.asyncio
    async def test_reason_no_memories(self, nemotron_service):
        """Test reasoning with no memories returns appropriate message."""
        answer, selected, sources, actions = await nemotron_service.reason("What was the AWS invoice amount?", [])

        assert answer is not None
        assert "couldn't find any relevant memories" in answer.lower()
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_missing_api_key(self, nemotron_service):
        nemotron_service.settings.NVIDIA_API_KEY = ""
        answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1"}])

        assert answer is None
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_missing_model(self, nemotron_service):
        nemotron_service.settings.NEMOTRON_MODEL = ""
        answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1"}])

        assert answer is None
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_http_error(self, nemotron_service):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        nemotron_service.set_client(AsyncMock(post=AsyncMock(return_value=mock_response)))

        answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1", "s3_key": "test.jpg"}])

        assert answer is None
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_timeout(self, nemotron_service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        nemotron_service.set_client(mock_client)

        answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1", "s3_key": "test.jpg"}])

        assert answer is None
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_malformed_response_no_choices(self, nemotron_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        nemotron_service.set_client(mock_client)

        # Mock S3 to avoid real S3 calls
        with patch("app.services.nemotron.get_async_s3_client") as mock_s3_client:
            mock_s3 = AsyncMock()
            mock_s3.get_object = AsyncMock(return_value={
                "Body": AsyncMock(read=AsyncMock(return_value=b"fake_image_bytes"))
            })
            mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
            mock_s3.__aexit__ = AsyncMock(return_value=None)
            mock_s3_client.return_value = mock_s3

            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")

                answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1", "s3_key": "test.jpg"}])

        # When LLM returns malformed response, agent should return fallback answer
        assert answer is not None
        assert "couldn't find any relevant information" in answer.lower()
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_malformed_response_empty_choices(self, nemotron_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        nemotron_service.set_client(mock_client)

        # Mock S3 to avoid real S3 calls
        with patch("app.services.nemotron.get_async_s3_client") as mock_s3_client:
            mock_s3 = AsyncMock()
            mock_s3.get_object = AsyncMock(return_value={
                "Body": AsyncMock(read=AsyncMock(return_value=b"fake_image_bytes"))
            })
            mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
            mock_s3.__aexit__ = AsyncMock(return_value=None)
            mock_s3_client.return_value = mock_s3

            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")

                answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1", "s3_key": "test.jpg"}])

        assert answer is not None
        assert "couldn't find any relevant information" in answer.lower()
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_reason_malformed_response_missing_content(self, nemotron_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {}}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        nemotron_service.set_client(mock_client)

        # Mock S3 to avoid real S3 calls
        with patch("app.services.nemotron.get_async_s3_client") as mock_s3_client:
            mock_s3 = AsyncMock()
            mock_s3.get_object = AsyncMock(return_value={
                "Body": AsyncMock(read=AsyncMock(return_value=b"fake_image_bytes"))
            })
            mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
            mock_s3.__aexit__ = AsyncMock(return_value=None)
            mock_s3_client.return_value = mock_s3

            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")

                answer, selected, sources, actions = await nemotron_service.reason("test query", [{"memory_id": "mem_1", "s3_key": "test.jpg"}])

        assert answer is not None
        assert "couldn't find any relevant information" in answer.lower()
        assert selected == []
        assert sources == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_get_s3_image_base64_success(self, nemotron_service):
        mock_s3 = AsyncMock()
        mock_s3.get_object = AsyncMock(return_value={
            "Body": AsyncMock(read=AsyncMock(return_value=b"fake_image_bytes"))
        })
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.nemotron.get_async_s3_client", return_value=mock_s3):
            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")
                image_b64 = await nemotron_service.get_s3_image_base64("memories/mem_1/original.jpg")

        assert image_b64 is not None
        assert isinstance(image_b64, str)

    @pytest.mark.asyncio
    async def test_get_s3_image_base64_failure(self, nemotron_service):
        mock_s3 = AsyncMock()
        mock_s3.get_object = AsyncMock(side_effect=Exception("S3 error"))
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.nemotron.get_async_s3_client", return_value=mock_s3):
            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")
                image_b64 = await nemotron_service.get_s3_image_base64("memories/mem_1/original.jpg")

        assert image_b64 is None

    @pytest.mark.asyncio
    async def test_build_reasoning_prompt(self, nemotron_service):
        memories = [
            {
                "memory_id": "mem_1",
                "distance": 0.1,
                "ocr_text": "AWS Invoice $2,499",
                "s3_key": "memories/mem_1/original.jpg",
                "original_filename": "invoice.jpg",
                "image_b64": "base64_image_data",
            }
        ]

        messages = nemotron_service._build_reasoning_prompt("What was the AWS invoice amount?", memories)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "memory collection" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "AWS invoice" in messages[1]["content"][0]["text"]
        assert "mem_1" in messages[1]["content"][1]["text"]
        assert "invoice.jpg" in messages[1]["content"][1]["text"]

    @pytest.mark.asyncio
    async def test_get_s3_image_base64_failure(self, nemotron_service):
        mock_s3 = AsyncMock()
        mock_s3.get_object = AsyncMock(side_effect=Exception("S3 error"))
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.nemotron.get_async_s3_client", return_value=mock_s3):
            with patch("app.services.nemotron.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(S3_BUCKET="test-bucket")
                image_b64 = await nemotron_service.get_s3_image_base64("memories/mem_1/original.jpg")

        assert image_b64 is None
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.storage import (
    generate_memory_id,
    get_s3_key,
    validate_file,
)


def test_generate_memory_id():
    mem_id = generate_memory_id()
    assert mem_id.startswith("mem_")
    assert len(mem_id) == 20  # "mem_" + 16 hex chars


def test_get_s3_key():
    mem_id = "mem_abc123"
    mime_type = "image/png"
    key = get_s3_key(mem_id, mime_type)
    assert key == "memories/mem_abc123/original.png"


def test_get_s3_key_various_mime_types():
    mem_id = "mem_test"
    assert get_s3_key(mem_id, "image/jpeg") == "memories/mem_test/original.jpg"
    assert get_s3_key(mem_id, "image/png") == "memories/mem_test/original.png"
    assert get_s3_key(mem_id, "image/webp") == "memories/mem_test/original.webp"
    assert get_s3_key(mem_id, "image/gif") == "memories/mem_test/original.gif"
    assert get_s3_key(mem_id, "image/heic") == "memories/mem_test/original.heic"
    assert get_s3_key(mem_id, "image/heif") == "memories/mem_test/original.heif"
    assert get_s3_key(mem_id, "application/pdf") == "memories/mem_test/original.bin"


def test_validate_file_success():
    settings = Settings(
        MAX_FILE_SIZE_MB=10,
        ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
    )
    with patch("app.services.storage.get_settings", return_value=settings):
        validate_file("test.jpg", "image/jpeg", 1024 * 1024)  # 1MB


def test_validate_file_invalid_mime_type():
    settings = Settings(
        MAX_FILE_SIZE_MB=10,
        ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
    )
    with patch("app.services.storage.get_settings", return_value=settings):
        with pytest.raises(Exception) as exc_info:
            validate_file("test.pdf", "application/pdf", 1024)
        assert "MIME type not allowed" in str(exc_info.value)


def test_validate_file_too_large():
    settings = Settings(
        MAX_FILE_SIZE_MB=1,
        ALLOWED_MIME_TYPES=["image/jpeg", "image/png"],
    )
    with patch("app.services.storage.get_settings", return_value=settings):
        with pytest.raises(Exception) as exc_info:
            validate_file("test.jpg", "image/jpeg", 2 * 1024 * 1024)  # 2MB
        assert "File too large" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_presigned_upload_url():
    from app.services.storage import generate_presigned_upload_url

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.generate_presigned_url = AsyncMock(return_value="https://presigned-url.example.com")

    with patch("app.services.storage.get_async_s3_client", return_value=mock_client):
        with patch("app.services.storage.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                S3_BUCKET="test-bucket",
                PRESIGNED_URL_EXPIRY_SECONDS=3600,
                MAX_FILE_SIZE_MB=10,
                ALLOWED_MIME_TYPES=["image/jpeg"],
            )
            url, s3_key, expires = await generate_presigned_upload_url(
                "mem_test", "test.jpg", "image/jpeg"
            )

    assert url == "https://presigned-url.example.com"
    assert s3_key == "memories/mem_test/original.jpg"
    assert expires == 3600
    mock_client.generate_presigned_url.assert_called_once()


@pytest.mark.asyncio
async def test_generate_presigned_download_url():
    from app.services.storage import generate_presigned_download_url

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.generate_presigned_url = AsyncMock(return_value="https://download-url.example.com")

    with patch("app.services.storage.get_async_s3_client", return_value=mock_client):
        with patch("app.services.storage.get_settings") as mock_settings:
            mock_settings.return_value = Settings(S3_BUCKET="test-bucket")
            url = await generate_presigned_download_url("memories/mem_test/original.jpg")

    assert url == "https://download-url.example.com"

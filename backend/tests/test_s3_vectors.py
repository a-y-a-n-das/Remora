import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError
from app.services.s3_vectors import S3VectorsService, S3VectorsError


@pytest.fixture
def mock_settings():
    with patch("app.services.s3_vectors.get_settings") as mock:
        mock.return_value = MagicMock(
            S3_VECTORS_BUCKET="test-vectors-bucket",
            S3_VECTORS_INDEX="memories",
            S3_VECTORS_DIMENSION=1024,
            S3_VECTORS_DISTANCE_METRIC="cosine",
            S3_VECTORS_MAX_RETRIES=3,
        )
        yield mock


@pytest.fixture
def s3_vectors_service(mock_settings):
    return S3VectorsService()


@pytest.fixture
def mock_client():
    mock = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def setup_client(s3_vectors_service, mock_client):
    s3_vectors_service.client = mock_client
    yield
    s3_vectors_service.client = None


class TestS3VectorsService:
    def test_validate_dimension_success(self, s3_vectors_service):
        vector = [0.1] * 1024
        s3_vectors_service._validate_dimension(vector)  # Should not raise

    def test_validate_dimension_failure(self, s3_vectors_service):
        vector = [0.1] * 512
        with pytest.raises(S3VectorsError) as exc_info:
            s3_vectors_service._validate_dimension(vector)
        assert "dimension mismatch" in str(exc_info.value)
        assert exc_info.value.retryable is False

    def test_validate_config_missing_bucket(self, s3_vectors_service):
        s3_vectors_service.bucket_name = ""
        error = s3_vectors_service._validate_config()
        assert "S3_VECTORS_BUCKET not configured" in error

    def test_validate_config_missing_index(self, s3_vectors_service):
        s3_vectors_service.index_name = ""
        error = s3_vectors_service._validate_config()
        assert "S3_VECTORS_INDEX not configured" in error

    def test_is_available(self, s3_vectors_service):
        s3_vectors_service.bucket_name = "test-bucket"
        s3_vectors_service.index_name = "test-index"
        assert s3_vectors_service.is_available() is True

        s3_vectors_service.bucket_name = ""
        assert s3_vectors_service.is_available() is False

    @pytest.mark.asyncio
    async def test_upsert_vector_success(self, s3_vectors_service):
        vector = [0.1] * 1024
        metadata = {"content_type": "image/jpeg"}

        s3_vectors_service.client.put_vectors = MagicMock()

        result = await s3_vectors_service.upsert_vector("mem_abc123", vector, metadata)

        assert result is True
        s3_vectors_service.client.put_vectors.assert_called_once()
        call_args = s3_vectors_service.client.put_vectors.call_args
        assert call_args.kwargs["vectorBucketName"] == "test-vectors-bucket"
        assert call_args.kwargs["indexName"] == "memories"
        assert len(call_args.kwargs["vectors"]) == 1
        assert call_args.kwargs["vectors"][0]["key"] == "mem_abc123"
        assert call_args.kwargs["vectors"][0]["data"]["float32"] == vector
        assert call_args.kwargs["vectors"][0]["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_upsert_vector_dimension_mismatch(self, s3_vectors_service):
        vector = [0.1] * 512  # Wrong dimension

        with pytest.raises(S3VectorsError) as exc_info:
            await s3_vectors_service.upsert_vector("mem_abc123", vector)
        assert "dimension mismatch" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_upsert_vector_missing_config(self, s3_vectors_service):
        s3_vectors_service.bucket_name = ""

        result = await s3_vectors_service.upsert_vector("mem_abc123", [0.1] * 1024)

        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_vector_validation_error(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid vector"}},
            "PutVectors",
        )
        s3_vectors_service.client.put_vectors.side_effect = error

        result = await s3_vectors_service.upsert_vector("mem_abc123", [0.1] * 1024)

        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_vector_resource_not_found(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Index not found"}},
            "PutVectors",
        )
        s3_vectors_service.client.put_vectors.side_effect = error

        result = await s3_vectors_service.upsert_vector("mem_abc123", [0.1] * 1024)

        assert result is False

    @pytest.mark.asyncio
    async def test_upsert_vectors_batch_success(self, s3_vectors_service):
        vectors = [
            {"memory_id": "mem_1", "vector": [0.1] * 1024},
            {"memory_id": "mem_2", "vector": [0.2] * 1024, "metadata": {"type": "image"}},
        ]

        s3_vectors_service.client.put_vectors = MagicMock()

        result = await s3_vectors_service.upsert_vectors(vectors)

        assert result is True
        s3_vectors_service.client.put_vectors.assert_called_once()
        call_args = s3_vectors_service.client.put_vectors.call_args
        assert len(call_args.kwargs["vectors"]) == 2

    @pytest.mark.asyncio
    async def test_upsert_vectors_dimension_mismatch(self, s3_vectors_service):
        vectors = [
            {"memory_id": "mem_1", "vector": [0.1] * 1024},
            {"memory_id": "mem_2", "vector": [0.1] * 512},  # Wrong dimension
        ]

        with pytest.raises(S3VectorsError) as exc_info:
            await s3_vectors_service.upsert_vectors(vectors)
        assert "dimension mismatch" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_query_vectors_success(self, s3_vectors_service):
        query_vector = [0.1] * 1024

        mock_response = {
            "vectors": [
                {"key": "mem_1", "distance": 0.1, "metadata": {"type": "image"}},
                {"key": "mem_2", "distance": 0.2, "metadata": {"type": "document"}},
            ]
        }
        s3_vectors_service.client.query_vectors = MagicMock(return_value=mock_response)

        results = await s3_vectors_service.query_vectors(query_vector, top_k=10)

        assert len(results) == 2
        assert results[0]["memory_id"] == "mem_1"
        assert results[0]["distance"] == 0.1
        assert results[0]["metadata"] == {"type": "image"}
        assert results[1]["memory_id"] == "mem_2"
        assert results[1]["distance"] == 0.2

    @pytest.mark.asyncio
    async def test_query_vectors_empty_results(self, s3_vectors_service):
        query_vector = [0.1] * 1024
        mock_response = {"vectors": []}
        s3_vectors_service.client.query_vectors = MagicMock(return_value=mock_response)

        results = await s3_vectors_service.query_vectors(query_vector, top_k=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_query_vectors_dimension_mismatch(self, s3_vectors_service):
        query_vector = [0.1] * 512  # Wrong dimension

        with pytest.raises(S3VectorsError) as exc_info:
            await s3_vectors_service.query_vectors(query_vector, top_k=10)
        assert "dimension mismatch" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_query_vectors_missing_config(self, s3_vectors_service):
        s3_vectors_service.bucket_name = ""

        results = await s3_vectors_service.query_vectors([0.1] * 1024, top_k=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_query_vectors_validation_error(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid query vector"}},
            "QueryVectors",
        )
        s3_vectors_service.client.query_vectors.side_effect = error

        results = await s3_vectors_service.query_vectors([0.1] * 1024, top_k=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_query_vectors_resource_not_found(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Index not found"}},
            "QueryVectors",
        )
        s3_vectors_service.client.query_vectors.side_effect = error

        results = await s3_vectors_service.query_vectors([0.1] * 1024, top_k=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_get_vectors_success(self, s3_vectors_service):
        mock_response = {
            "vectors": [
                {"key": "mem_1", "data": {"float32": [0.1] * 1024}, "metadata": {"type": "image"}},
                {"key": "mem_2", "data": {"float32": [0.2] * 1024}},
            ]
        }
        s3_vectors_service.client.get_vectors = MagicMock(return_value=mock_response)

        results = await s3_vectors_service.get_vectors(["mem_1", "mem_2"])

        assert len(results) == 2
        assert results[0]["key"] == "mem_1"
        assert results[0]["vector"] == [0.1] * 1024
        assert results[0]["metadata"] == {"type": "image"}
        assert results[1]["key"] == "mem_2"
        assert results[1]["vector"] == [0.2] * 1024

    @pytest.mark.asyncio
    async def test_get_vectors_resource_not_found(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetVectors",
        )
        s3_vectors_service.client.get_vectors.side_effect = error

        results = await s3_vectors_service.get_vectors(["mem_1"])

        assert results == []

    @pytest.mark.asyncio
    async def test_delete_vectors_success(self, s3_vectors_service):
        s3_vectors_service.client.delete_vectors = MagicMock()

        result = await s3_vectors_service.delete_vectors(["mem_1", "mem_2"])

        assert result is True
        s3_vectors_service.client.delete_vectors.assert_called_once_with(
            vectorBucketName="test-vectors-bucket",
            indexName="memories",
            keys=["mem_1", "mem_2"],
        )

    @pytest.mark.asyncio
    async def test_delete_vectors_resource_not_found(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteVectors",
        )
        s3_vectors_service.client.delete_vectors.side_effect = error

        result = await s3_vectors_service.delete_vectors(["mem_1"])

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_vectors_validation_error(self, s3_vectors_service):
        error = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid keys"}},
            "DeleteVectors",
        )
        s3_vectors_service.client.delete_vectors.side_effect = error

        result = await s3_vectors_service.delete_vectors(["mem_1"])

        assert result is False
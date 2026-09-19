import time
from typing import Optional, List, Dict, Any
import botocore.exceptions
from app.core.aws_clients import get_s3_vectors_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3VectorsError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        self.retryable = retryable
        super().__init__(message)


class S3VectorsService:
    def __init__(self):
        self.client = get_s3_vectors_client()
        self.settings = get_settings()
        self.bucket_name = self.settings.S3_VECTORS_BUCKET
        self.index_name = self.settings.S3_VECTORS_INDEX
        self.dimension = self.settings.S3_VECTORS_DIMENSION
        self.distance_metric = self.settings.S3_VECTORS_DISTANCE_METRIC

    def _validate_dimension(self, vector: List[float]) -> None:
        if len(vector) != self.dimension:
            raise S3VectorsError(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}",
                retryable=False,
            )

    def _validate_config(self) -> Optional[str]:
        if not self.bucket_name:
            return "S3_VECTORS_BUCKET not configured"
        if not self.index_name:
            return "S3_VECTORS_INDEX not configured"
        return None

    def is_available(self) -> bool:
        return bool(self.bucket_name and self.index_name)

    def _handle_client_error(self, e: botocore.exceptions.ClientError, operation: str, context: str = "") -> bool:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationException":
            logger.error(f"s3_vectors_{operation}_validation_error", error=str(e), context=context)
            return False
        elif error_code == "ResourceNotFoundException":
            logger.error(f"s3_vectors_{operation}_resource_not_found", error=str(e), context=context)
            return False
        elif error_code == "ThrottlingException":
            logger.error(f"s3_vectors_{operation}_throttled", error=str(e), context=context)
            raise
        else:
            logger.error(f"s3_vectors_{operation}_failed", error=str(e), context=context)
            return False

    def _handle_client_error_list(self, e: botocore.exceptions.ClientError, operation: str, context: str = "") -> List:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationException":
            logger.error(f"s3_vectors_{operation}_validation_error", error=str(e), context=context)
            return []
        elif error_code == "ResourceNotFoundException":
            logger.error(f"s3_vectors_{operation}_resource_not_found", error=str(e), context=context)
            return []
        elif error_code == "ThrottlingException":
            logger.error(f"s3_vectors_{operation}_throttled", error=str(e), context=context)
            raise
        else:
            logger.error(f"s3_vectors_{operation}_failed", error=str(e), context=context)
            return []

    async def upsert_vector(
        self,
        memory_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        config_error = self._validate_config()
        if config_error:
            logger.error("s3_vectors_config_missing", error=config_error)
            return False

        self._validate_dimension(vector)

        start_time = time.time()

        try:
            vector_data = {
                "key": memory_id,
                "data": {"float32": vector},
            }

            if metadata:
                vector_data["metadata"] = metadata

            self.client.put_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                vectors=[vector_data],
            )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "s3_vectors_upserted",
                memory_id=memory_id,
                dimension=len(vector),
                duration_ms=duration_ms,
            )
            return True

        except botocore.exceptions.ClientError as e:
            return self._handle_client_error(e, "upsert", memory_id)

    async def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
    ) -> bool:
        config_error = self._validate_config()
        if config_error:
            logger.error("s3_vectors_config_missing", error=config_error)
            return False

        for v in vectors:
            self._validate_dimension(v["vector"])

        start_time = time.time()

        try:
            vector_data_list = []
            for v in vectors:
                vector_data = {
                    "key": v["memory_id"],
                    "data": {"float32": v["vector"]},
                }
                if "metadata" in v:
                    vector_data["metadata"] = v["metadata"]
                vector_data_list.append(vector_data)

            self.client.put_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                vectors=vector_data_list,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "s3_vectors_batch_upserted",
                count=len(vectors),
                duration_ms=duration_ms,
            )
            return True

        except botocore.exceptions.ClientError as e:
            return self._handle_client_error(e, "upsert")

    async def query_vectors(
        self,
        query_vector: List[float],
        top_k: int = 10,
        return_metadata: bool = True,
        return_distance: bool = True,
    ) -> List[Dict[str, Any]]:
        config_error = self._validate_config()
        if config_error:
            logger.error("s3_vectors_config_missing", error=config_error)
            return []

        self._validate_dimension(query_vector)

        start_time = time.time()

        try:
            response = self.client.query_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                topK=top_k,
                queryVector={"float32": query_vector},
                returnMetadata=True,
                returnDistance=True,
            )

            results = []
            for item in response.get("vectors", []):
                result = {
                    "memory_id": item["key"],
                    "distance": item.get("distance"),
                }
                if "metadata" in item:
                    result["metadata"] = item["metadata"]
                results.append(result)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "s3_vectors_queried",
                results=len(results),
                top_k=top_k,
                duration_ms=duration_ms,
            )
            return results

        except botocore.exceptions.ClientError as e:
            return self._handle_client_error_list(e, "query")

    async def get_vectors(self, memory_ids: List[str]) -> List[Dict[str, Any]]:
        config_error = self._validate_config()
        if config_error:
            logger.error("s3_vectors_config_missing", error=config_error)
            return []

        try:
            response = self.client.get_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                keys=memory_ids,
            )

            results = []
            for item in response.get("vectors", []):
                result = {"key": item["key"], "vector": item["data"]["float32"]}
                if "metadata" in item:
                    result["metadata"] = item["metadata"]
                results.append(result)

            return results

        except botocore.exceptions.ClientError as e:
            return self._handle_client_error_list(e, "get")

    async def delete_vectors(self, memory_ids: List[str]) -> bool:
        config_error = self._validate_config()
        if config_error:
            logger.error("s3_vectors_config_missing", error=config_error)
            return False

        try:
            self.client.delete_vectors(
                vectorBucketName=self.bucket_name,
                indexName=self.index_name,
                keys=memory_ids,
            )
            return True

        except botocore.exceptions.ClientError as e:
            return self._handle_client_error(e, "delete")


s3_vectors_service = S3VectorsService()
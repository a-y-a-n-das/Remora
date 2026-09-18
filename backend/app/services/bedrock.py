import base64
import json
import time
from typing import Optional, List
from app.core.aws_clients import get_bedrock_runtime_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BedrockEmbeddingService:
    def __init__(self):
        self.client = get_bedrock_runtime_client()
        self.settings = get_settings()

    def get_multimodal_embedding(
        self, s3_bucket: str, s3_key: str, ocr_text: Optional[str] = None
    ) -> Optional[List[float]]:
        model_id = self.settings.BEDROCK_EMBEDDING_MODEL_ID
        expected_dim = self.settings.BEDROCK_EMBEDDING_DIMENSION

        start_time = time.time()

        try:
            if "titan-embed-image" in model_id:
                embedding = self._get_titan_image_embedding(s3_bucket, s3_key, ocr_text)
            else:
                logger.warning("unsupported_embedding_model", model_id=model_id)
                return None

            if embedding is None:
                return None

            if len(embedding) != expected_dim:
                logger.error(
                    "embedding_dimension_mismatch",
                    expected=expected_dim,
                    actual=len(embedding),
                    model_id=model_id,
                )
                return None

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "bedrock_embedding_generated",
                model_id=model_id,
                dimension=len(embedding),
                duration_ms=duration_ms,
            )
            return embedding

        except self.client.exceptions.ThrottlingException as e:
            logger.error("bedrock_throttled", model_id=model_id, error=str(e))
            raise
        except Exception as e:
            logger.error("bedrock_embedding_failed", model_id=model_id, error=str(e))
            raise

    def _get_titan_image_embedding(
        self, s3_bucket: str, s3_key: str, ocr_text: Optional[str]
    ) -> Optional[List[float]]:
        from app.core.aws_clients import get_s3_client

        s3 = get_s3_client()
        try:
            obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
            image_bytes = obj["Body"].read()
        except Exception as e:
            logger.error("bedrock_s3_read_failed", s3_key=s3_key, error=str(e))
            return None

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        body = {"inputImage": image_b64}
        if ocr_text:
            body["inputText"] = ocr_text[:2048]

        response = self.client.invoke_model(
            modelId=self.settings.BEDROCK_EMBEDDING_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body.get("embedding")


bedrock_embedding_service = BedrockEmbeddingService()
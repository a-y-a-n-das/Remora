import base64
import time
from typing import Optional, List
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

VOYAGE_API_BASE = "https://api.voyageai.com/v1"


class VoyageEmbeddingService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=VOYAGE_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.settings.VOYAGE_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.settings.VOYAGE_TIMEOUT_SECONDS),
            )
        return self._client

    def set_client(self, client: httpx.AsyncClient) -> None:
        """Inject a client for testing."""
        self._client = client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _validate_config(self) -> Optional[str]:
        if not self.settings.VOYAGE_API_KEY:
            return "VOYAGE_API_KEY not configured"
        if not self.settings.VOYAGE_MODEL:
            return "VOYAGE_MODEL not configured"
        return None

    def _validate_embedding(self, embedding: List[float], context: str) -> bool:
        expected_dim = self.settings.VOYAGE_EMBEDDING_DIMENSION
        if len(embedding) != expected_dim:
            logger.error(
                "embedding_dimension_mismatch",
                context=context,
                expected=expected_dim,
                actual=len(embedding),
            )
            return False
        return True

    async def get_image_embedding(
        self, image_bytes: bytes, text: Optional[str] = None
    ) -> Optional[List[float]]:
        config_error = self._validate_config()
        if config_error:
            logger.error("voyage_config_missing", error=config_error)
            return None

        start_time = time.time()

        try:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            input_data = [{"image": image_b64}]
            if text:
                input_data.append({"text": text[:2048]})

            payload = {
                "model": self.settings.VOYAGE_MODEL,
                "input": input_data,
            }

            response = await self.client.post("/multimodal/embed", json=payload)
            response.raise_for_status()

            data = response.json()

            embeddings = data.get("data", [])
            if not embeddings:
                logger.error("voyage_no_embeddings_returned", model=self.settings.VOYAGE_MODEL)
                return None

            embedding = embeddings[0].get("embedding")
            if embedding is None:
                logger.error("voyage_embedding_missing_in_response", response=data)
                return None

            if not self._validate_embedding(embedding, "image"):
                return None

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "voyage_image_embedding_generated",
                model=self.settings.VOYAGE_MODEL,
                dimension=len(embedding),
                duration_ms=duration_ms,
            )
            return embedding

        except httpx.TimeoutException:
            logger.error("voyage_timeout", model=self.settings.VOYAGE_MODEL)
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                "voyage_http_error",
                model=self.settings.VOYAGE_MODEL,
                status_code=e.response.status_code,
                response=e.response.text[:500],
            )
            return None
        except Exception as e:
            logger.error("voyage_embedding_failed", error=str(e))
            return None

    async def get_text_embedding(self, text: str) -> Optional[List[float]]:
        config_error = self._validate_config()
        if config_error:
            logger.error("voyage_config_missing", error=config_error)
            return None

        if not text or not text.strip():
            logger.error("voyage_empty_text_input")
            return None

        start_time = time.time()

        try:
            payload = {
                "model": self.settings.VOYAGE_MODEL,
                "input": [{"text": text[:2048]}],
            }

            response = await self.client.post("/multimodal/embed", json=payload)
            response.raise_for_status()

            data = response.json()

            embeddings = data.get("data", [])
            if not embeddings:
                logger.error("voyage_no_embeddings_returned", model=self.settings.VOYAGE_MODEL)
                return None

            embedding = embeddings[0].get("embedding")
            if embedding is None:
                logger.error("voyage_embedding_missing_in_response", response=data)
                return None

            if not self._validate_embedding(embedding, "text"):
                return None

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "voyage_text_embedding_generated",
                model=self.settings.VOYAGE_MODEL,
                dimension=len(embedding),
                duration_ms=duration_ms,
            )
            return embedding

        except httpx.TimeoutException:
            logger.error("voyage_timeout", model=self.settings.VOYAGE_MODEL)
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                "voyage_http_error",
                model=self.settings.VOYAGE_MODEL,
                status_code=e.response.status_code,
                response=e.response.text[:500],
            )
            return None
        except Exception as e:
            logger.error("voyage_embedding_failed", error=str(e))
            return None


voyage_embedding_service = VoyageEmbeddingService()
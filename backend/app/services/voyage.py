import asyncio
import base64
import time
from typing import Optional, List
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

VOYAGE_API_BASE = "https://api.voyageai.com/v1"
TRANSIENT_STATUS_CODES = {408, 429}
MAX_RETRY_DELAY_SECONDS = 60.0


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

    async def _post_with_retries(self, payload: dict, context: str) -> httpx.Response | None:
        max_retries = max(0, self.settings.VOYAGE_MAX_RETRIES)
        attempt = 0

        while True:
            try:
                response = await self.client.post("/multimodalembeddings", json=payload)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                retryable = status_code in TRANSIENT_STATUS_CODES or status_code >= 500
                if not retryable or attempt >= max_retries:
                    logger.error(
                        "voyage_http_error",
                        context=context,
                        model=self.settings.VOYAGE_MODEL,
                        status_code=status_code,
                        response=e.response.text[:500],
                    )
                    return None

                retry_after = e.response.headers.get("Retry-After")
                delay = None
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except (TypeError, ValueError):
                        delay = None
                if delay is None:
                    delay = 2 ** attempt
                delay = min(max(0.0, delay), MAX_RETRY_DELAY_SECONDS)
                logger.warning(
                    "voyage_transient_http_error_retrying",
                    context=context,
                    model=self.settings.VOYAGE_MODEL,
                    status_code=status_code,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            except httpx.TimeoutException:
                if attempt >= max_retries:
                    logger.error("voyage_timeout", context=context, model=self.settings.VOYAGE_MODEL)
                    return None
                delay = min(2 ** attempt, MAX_RETRY_DELAY_SECONDS)
                logger.warning(
                    "voyage_timeout_retrying",
                    context=context,
                    model=self.settings.VOYAGE_MODEL,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            except httpx.RequestError as e:
                if attempt >= max_retries:
                    logger.error(
                        "voyage_request_failed",
                        context=context,
                        model=self.settings.VOYAGE_MODEL,
                        error=str(e),
                    )
                    return None
                delay = min(2 ** attempt, MAX_RETRY_DELAY_SECONDS)
                logger.warning(
                    "voyage_request_retrying",
                    context=context,
                    model=self.settings.VOYAGE_MODEL,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error("voyage_embedding_failed", context=context, error=str(e))
                return None

            attempt += 1

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

            content = [{"type": "image_base64", "image_base64": f"data:image/jpeg;base64,{image_b64}"}]
            if text:
                content.insert(0, {"type": "text", "text": text[:2048]})

            payload = {
                "model": self.settings.VOYAGE_MODEL,
                "inputs": [{"content": content}],
            }

            response = await self._post_with_retries(payload, "image")
            if response is None:
                return None

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
                "inputs": [{"content": [{"type": "text", "text": text[:2048]}]}],
            }

            response = await self._post_with_retries(payload, "text")
            if response is None:
                return None

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

        except Exception as e:
            logger.error("voyage_embedding_failed", error=str(e))
            return None


voyage_embedding_service = VoyageEmbeddingService()
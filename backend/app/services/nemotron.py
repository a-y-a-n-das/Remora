import base64
import time
from typing import Optional, List, Dict, Any
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.storage import get_async_s3_client
from app.core.config import get_settings

logger = get_logger(__name__)

NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"


class NemotronService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.NVIDIA_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.settings.NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.settings.NEMOTRON_TIMEOUT_SECONDS),
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
        if not self.settings.NVIDIA_API_KEY:
            return "NVIDIA_API_KEY not configured"
        if not self.settings.NEMOTRON_MODEL:
            return "NEMOTRON_MODEL not configured"
        return None

    async def get_s3_image_base64(self, s3_key: str) -> Optional[str]:
        """Fetch image from S3 and return as base64 string."""
        settings = get_settings()
        client = get_async_s3_client()
        async with client as s3:
            try:
                response = await s3.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
                image_bytes = await response["Body"].read()
                return base64.b64encode(image_bytes).decode("utf-8")
            except Exception as e:
                logger.error("nemotron_s3_fetch_failed", s3_key=s3_key, error=str(e))
                return None

    def _build_reasoning_prompt(
        self,
        query: str,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build the message content for Nemotron with images and OCR context."""

        # System prompt
        system_prompt = (
            "You are an AI assistant helping a user find information from their personal visual memory collection. "
            "You will be given a user query and a set of retrieved memories, each containing an image and associated OCR text. "
            "Your task is to analyze the images and OCR text to answer the user's query as accurately as possible. "
            "IMPORTANT: You must inspect the actual images provided. The OCR text is supporting context and may be incomplete or contain errors. "
            "Rely on the actual visual content of the images as your primary source of truth. "
            "If the images do not contain relevant information for the query, state that clearly. "
            "Cite the specific memories (by their IDs or descriptions) that support your answer."
        )

        # Build user message with query and context
        user_content = [
            {
                "type": "text",
                "text": f"User Query: {query}\n\nRetrieved Memories:"
            }
        ]

        for i, memory in enumerate(memories):
            memory_id = memory.get("memory_id", "unknown")
            ocr_text = memory.get("ocr_text", "")
            s3_key = memory.get("s3_key", "")
            original_filename = memory.get("original_filename", "unknown")
            distance = memory.get("distance", 0.0)

            memory_section = {
                "type": "text",
                "text": f"\n--- Memory {i+1} (ID: {memory_id}, Distance: {distance:.3f}, File: {original_filename}) ---"
            }
            user_content.append(memory_section)

            # Add image
            image_b64 = memory.get("image_b64")
            if image_b64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                })

            # Add OCR text
            if ocr_text:
                ocr_section = {
                    "type": "text",
                    "text": f"OCR Text: {ocr_text[:2000]}" if len(ocr_text) > 2000 else f"OCR Text: {ocr_text}"
                }
                user_content.append(ocr_section)
            else:
                user_content.append({
                    "type": "text",
                    "text": "OCR Text: (none extracted)"
                })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        return messages

    async def reason(
        self,
        query: str,
        memories: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Perform multimodal reasoning with Nemotron on the given query and memories."""
        config_error = self._validate_config()
        if config_error:
            logger.error("nemotron_config_missing", error=config_error)
            return None

        if not memories:
            logger.info("nemotron_no_memories", query=query)
            return "I couldn't find any relevant memories for your query."

        start_time = time.time()

        try:
            # Fetch images from S3 for each memory
            enriched_memories = []
            for memory in memories:
                s3_key = memory.get("s3_key", "")
                image_b64 = None
                if s3_key:
                    image_b64 = await self.get_s3_image_base64(memory["s3_key"])
                enriched_memories.append({
                    **memory,
                    "image_b64": image_b64,
                })

            messages = self._build_reasoning_prompt(query, enriched_memories)

            payload = {
                "model": self.settings.NEMOTRON_MODEL,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.3,
                "top_p": 0.9,
            }

            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                logger.error("nemotron_no_choices_returned", model=self.settings.NEMOTRON_MODEL)
                return None

            message = choices[0].get("message", {})
            content = message.get("content")
            if content is None:
                logger.error("nemotron_empty_content", response=data)
                return None

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "nemotron_reasoning_completed",
                model=self.settings.NEMOTRON_MODEL,
                duration_ms=duration_ms,
                query_length=len(query),
                num_memories=len(memories),
            )
            return content

        except httpx.TimeoutException:
            logger.error("nemotron_timeout", model=self.settings.NEMOTRON_MODEL)
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                "nemotron_http_error",
                model=self.settings.NEMOTRON_MODEL,
                status_code=e.response.status_code,
                response=e.response.text[:500],
            )
            return None
        except Exception as e:
            logger.error("nemotron_reasoning_failed", error=str(e))
            return None


nemotron_service = NemotronService()
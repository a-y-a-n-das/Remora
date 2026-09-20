import base64
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.storage import get_async_s3_client
from app.services.tools import tool_registry, execute_tool, register_default_tools

logger = get_logger(__name__)

NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
MAX_TOOL_ITERATIONS = 5


class NemotronService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._client = client
        # Load prompt templates at initialization
        prompts_dir = Path(__file__).parent.parent / "prompts" / "nemotron"
        self._system_prompt = (Path(__file__).parent.parent / "prompts" / "nemotron" / "system.txt").read_text(encoding="utf-8")
        self._user_template = (Path(__file__).parent.parent / "prompts" / "nemotron" / "user_template.txt").read_text(encoding="utf-8")
        self._memory_item_template = (Path(__file__).parent.parent / "prompts" / "nemotron" / "memory_item.txt").read_text(encoding="utf-8")
        # Register default tools
        register_default_tools()

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
        system_prompt = self._system_prompt

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
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_content}
        ]

        return messages

    def _build_final_response_prompt(self) -> Dict[str, Any]:
        """Build a prompt asking the LLM to produce the final JSON response."""
        return {
            "role": "user",
            "content": "Now produce the final JSON response with the following structure:\n"
            "{\n"
            '  "answer": "Natural language answer to the user.",\n'
            '  "selected_memory_ids": [],\n'
            '  "sources": [],\n'
            '  "actions": []\n'
            "}\n\n"
            "Requirements:\n"
            "- answer: Natural language response. Never include memory IDs or internal IDs in the answer.\n"
            "- selected_memory_ids: Only candidate memory IDs that genuinely contributed to the answer.\n"
            "- sources: External sources from web research. Each: {title, url, description}.\n"
            "- actions: User-facing actions. For Google Calendar: {type: 'google_calendar', title, url, status: 'prepared'}.\n"
            "- Do not include internal IDs in answer text.\n"
            "- Return valid JSON only."
        }

    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call the LLM API and return the message."""
        payload = {
            "model": self.settings.NEMOTRON_MODEL,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
            "top_p": 0.9,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            logger.error("nemotron_no_choices_returned", model=self.settings.NEMOTRON_MODEL)
            return None

        message = choices[0].get("message", {})
        return message

    async def reason(
        self,
        query: str,
        memories: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Perform multimodal reasoning with Nemotron using tool-calling agent loop.

        Returns:
            Tuple of (answer, selected_memory_ids, sources, actions).
            If reasoning fails, returns (None, [], [], []).
        """
        config_error = self._validate_config()
        if config_error:
            logger.error("nemotron_config_missing", error=config_error)
            return None, [], [], []

        if not memories:
            logger.info("nemotron_no_memories", query=query)
            return "I couldn't find any relevant memories for your query.", [], [], []

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

            # Build initial messages
            messages = self._build_reasoning_prompt(query, enriched_memories)
            tools = tool_registry.get_tool_definitions()

            # Tool-calling agent loop
            tool_iterations = 0
            selected_memory_ids = []
            sources: List[Dict[str, Any]] = []
            actions: List[Dict[str, Any]] = []
            final_answer = None

            while tool_iterations < MAX_TOOL_ITERATIONS:
                tool_iterations += 1

                message = await self._call_llm(messages, tools)
                if message is None:
                    break

                # Check if LLM wants to call a tool
                tool_calls = message.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls - this should be the final response
                    content = message.get("content", "")
                    try:
                        parsed = json.loads(content)
                        final_answer = parsed.get("answer", "").strip()
                        selected_memory_ids = parsed.get("selected_memory_ids", [])
                        sources = parsed.get("sources", [])
                        actions = parsed.get("actions", [])

                        # Validate selected_memory_ids
                        if not isinstance(selected_memory_ids, list):
                            selected_memory_ids = []
                        else:
                            selected_memory_ids = [str(mid) for mid in selected_memory_ids if isinstance(mid, (str, int))]

                        # Validate sources
                        if not isinstance(sources, list):
                            sources = []

                        # Validate actions
                        if not isinstance(actions, list):
                            actions = []

                        break
                    except json.JSONDecodeError:
                        logger.warning("nemotron_non_json_response", content=content[:500])
                        # Not a valid JSON, continue loop
                        pass

                # Execute tool calls
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    arguments_str = function.get("arguments", "{}")

                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        arguments = {}

                    logger.info(f"Tool call: {tool_name}", arguments=arguments)

                    result = await execute_tool(tool_name, arguments)

                    # Add tool result to messages
                    messages.append({
                        "role": "assistant",
                        "content": message.get("content", ""),
                        "tool_calls": [tool_call],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": json.dumps(result),
                    })

                    # Track results for final response
                    if tool_name == "exa_web_search":
                        results = result.get("results", [])
                        for r in results:
                            if r.get("url") and r not in sources:
                                sources.append(r)
                    elif tool_name == "exa_web_fetch":
                        # Fetch results are already in conversation
                        pass
                    elif tool_name == "google_calendar_create_event":
                        if "url" in result:
                            actions.append({
                                "type": "google_calendar",
                                "title": result.get("title", ""),
                                "url": result["url"],
                                "status": "prepared",
                            })

            # If we exited loop without final answer, try to get one
            if final_answer is None:
                # Request final response
                messages.append(self._build_final_response_prompt())
                message = await self._call_llm(messages, None)
                if message:
                    content = message.get("content", "")
                    try:
                        parsed = json.loads(content)
                        final_answer = parsed.get("answer", "").strip()
                        selected_memory_ids = parsed.get("selected_memory_ids", [])
                        sources = parsed.get("sources", [])
                        actions = parsed.get("actions", [])
                    except json.JSONDecodeError:
                        final_answer = content.strip()

            # Validate final answer
            if not final_answer:
                logger.warning("nemotron_empty_answer")
                final_answer = "I couldn't find any relevant information in the provided memories."

            # Validate selected_memory_ids
            if not isinstance(selected_memory_ids, list):
                selected_memory_ids = []
            else:
                selected_memory_ids = [str(mid) for mid in selected_memory_ids if isinstance(mid, (str, int))]

            # Deduplicate while preserving order
            seen = set()
            unique_ids = []
            for mid in selected_memory_ids:
                if mid not in seen:
                    seen.add(mid)
                    unique_ids.append(mid)
            selected_memory_ids = unique_ids

            # Validate sources
            if not isinstance(sources, list):
                sources = []

            # Validate actions
            if not isinstance(actions, list):
                actions = []

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "nemotron_reasoning_completed",
                model=self.settings.NEMOTRON_MODEL,
                duration_ms=duration_ms,
                query_length=len(query),
                num_memories=len(memories),
                selected_count=len(selected_memory_ids),
                tool_iterations=tool_iterations,
                sources_count=len(sources),
                actions_count=len(actions),
            )
            return final_answer, selected_memory_ids, sources, actions

        except httpx.TimeoutException:
            logger.error("nemotron_timeout", model=self.settings.NEMOTRON_MODEL)
            return None, [], [], []
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 429:
                logger.error("nemotron_rate_limited", model=self.settings.NEMOTRON_MODEL)
            elif status_code >= 500:
                logger.error(
                    "nemotron_server_error",
                    model=self.settings.NEMOTRON_MODEL,
                    status_code=status_code,
                )
            else:
                logger.error(
                    "nemotron_http_error",
                    model=self.settings.NEMOTRON_MODEL,
                    status_code=status_code,
                    response=e.response.text[:500],
                )
            return None, [], [], []
        except Exception as e:
            logger.error("nemotron_reasoning_failed", error=str(e))
            return None, [], [], []


nemotron_service = NemotronService()
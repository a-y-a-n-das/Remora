import json
import httpx
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode, quote
import urllib.parse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas import Source, Action

logger = get_logger(__name__)


@dataclass
class Tool:
    """Represents a tool that can be called by the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class ToolRegistry:
    """Registry of available tools for the LLM."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]


# Global tool registry
tool_registry = ToolRegistry()


async def exa_web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search the web using Exa API."""
    settings = get_settings()
    exa_api_key = getattr(settings, "EXA_API_KEY", None)

    if not exa_api_key:
        logger.warning("EXA_API_KEY not configured")
        return {"results": [], "error": "Exa API not configured"}

    # Ensure query is a string (defensive: LLM might pass object)
    if not isinstance(query, str):
        logger.warning(f"exa_web_search received non-string query: {type(query)}, converting to string")
        query = str(query)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.exa.ai/search",
                headers={
                    "Authorization": f"Bearer {exa_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "numResults": num_results,
                    "useAutoprompt": True,
                    "type": "keyword",
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("text", "")[:300] if item.get("text") else "",
                })

            return {"results": results}
    except httpx.HTTPStatusError as e:
        logger.error(f"Exa search failed: {e.response.status_code} - {e.response.text}")
        return {"results": [], "error": f"Exa search failed: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Exa search error: {e}")
        return {"results": [], "error": str(e)}


async def exa_web_fetch(url: str) -> Dict[str, Any]:
    """Fetch a webpage using Exa API."""
    settings = get_settings()
    exa_api_key = getattr(settings, "EXA_API_KEY", None)

    if not exa_api_key:
        logger.warning("EXA_API_KEY not configured")
        return {"content": "", "error": "Exa API not configured"}

    # Ensure url is a string (defensive: LLM might pass object)
    if not isinstance(url, str):
        logger.warning(f"exa_web_fetch received non-string url: {type(url)}, converting to string")
        url = str(url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.exa.ai/contents",
                headers={
                    "Authorization": f"Bearer {exa_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "ids": [url],
                    "text": True,
                    "highlights": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if results:
                content = results[0].get("text", "")
                highlights = results[0].get("highlights", [])
                return {
                    "content": content[:5000] if content else "",
                    "highlights": highlights[:5] if highlights else [],
                }

            return {"content": "", "error": "No content found"}
    except httpx.HTTPStatusError as e:
        logger.error(f"Exa fetch failed: {e.response.status_code} - {e.response.text}")
        return {"content": "", "error": f"Exa fetch failed: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Exa fetch error: {e}")
        return {"content": "", "error": str(e)}


async def google_calendar_create_event(
    title: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a Google Calendar event URL."""
    try:
        # Parse and validate datetime strings
        start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))

        if end_dt <= start_dt:
            return {"error": "End time must be after start time"}

        # Build Google Calendar URL
        base_url = "https://calendar.google.com/calendar/render"

        params = {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{start_dt.strftime('%Y%m%dT%H%M%SZ')}/{end_dt.strftime('%Y%m%dT%H%M%SZ')}",
        }

        if description:
            params["details"] = description
        if location:
            params["location"] = location

        url = f"{base_url}?{urlencode(params, quote_via=quote)}"

        return {
            "url": url,
            "title": title,
            "start": start_datetime,
            "end": end_datetime,
            "description": description,
            "location": location,
        }
    except ValueError as e:
        logger.error(f"Invalid datetime format: {e}")
        return {"error": f"Invalid datetime format: {e}"}
    except Exception as e:
        logger.error(f"Calendar URL generation failed: {e}")
        return {"error": str(e)}


# Register tools
def register_default_tools() -> None:
    """Register all default tools with the registry."""

    # Exa web search
    tool_registry.register(Tool(
        name="exa_web_search",
        description="Search the web for current information. Use when you need current prices, availability, reviews, news, specifications, or other information that may have changed since the memories were created. Returns a list of results with title, URL, and description.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
        handler=exa_web_search,
    ))

    # Exa web fetch
    tool_registry.register(Tool(
        name="exa_web_fetch",
        description="Fetch the full content of a specific webpage. Use when you need to read the actual content of a specific URL found in search results.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
            "required": ["url"],
        },
        handler=exa_web_fetch,
    ))

    # Google Calendar
    tool_registry.register(Tool(
        name="google_calendar_create_event",
        description="Prepare a Google Calendar event URL for the user to open and save. Use when the user asks to schedule, add to calendar, or remind them about something. Returns a URL the user can open to save the event. The event is PREPARED not executed - the user must open the link to save it.",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Start date/time in ISO format (e.g., '2024-01-15T10:00:00Z')",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "End date/time in ISO format (e.g., '2024-01-15T11:00:00Z')",
                },
                "description": {
                    "type": "string",
                    "description": "Event description",
                },
                "location": {
                    "type": "string",
                    "description": "Event location",
                },
            },
            "required": ["title", "start_datetime", "end_datetime"],
        },
        handler=google_calendar_create_event,
    ))


async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with given arguments."""
    tool = tool_registry.get_tool(name)
    if not tool:
        return {"error": f"Tool '{name}' not found"}

    try:
        result = await tool.handler(arguments)
        return result
    except Exception as e:
        logger.error(f"Tool '{name}' execution failed: {e}")
        return {"error": f"Tool execution failed: {e}"}
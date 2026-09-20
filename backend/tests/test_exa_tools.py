import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.tools import (
    exa_web_search,
    exa_web_fetch,
    google_calendar_create_event,
    tool_registry,
    Tool,
    execute_tool,
    register_default_tools,
)
from app.core.config import get_settings


class TestExaTools:
    """Tests for Exa web search and fetch tools."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear the tool registry before each test."""
        tool_registry._tools.clear()
        yield
        tool_registry._tools.clear()

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with EXA_API_KEY."""
        settings = MagicMock()
        settings.EXA_API_KEY = "test-exa-api-key"
        settings.EXA_API_BASE = "https://api.exa.ai"
        return settings

    @pytest.mark.asyncio
    async def test_exa_web_search_uses_api_key_from_config(self, mock_settings):
        """Test that exa_web_search reads EXA_API_KEY from configuration."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "results": [
                    {"title": "Test Result", "url": "https://example.com", "text": "Test content"}
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_search("test query", num_results=5)

            # Verify the API key was used in the Authorization header
            mock_client.post.assert_awaited_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-exa-api-key"
            assert call_args[1]["json"]["query"] == "test query"
            assert call_args[1]["json"]["numResults"] == 5

    @pytest.mark.asyncio
    async def test_exa_web_search_missing_api_key(self):
        """Test graceful handling when EXA_API_KEY is missing."""
        mock_settings = MagicMock()
        mock_settings.EXA_API_KEY = ""

        with patch("app.services.tools.get_settings", return_value=mock_settings):
            result = await exa_web_search("test query")

        assert result == {"results": [], "error": "Exa API not configured"}

    @pytest.mark.asyncio
    async def test_exa_web_search_http_error(self, mock_settings):
        """Test handling of HTTP errors from Exa API."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
            )

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_search("test query")

        assert result == {"results": [], "error": "Exa search failed: 401"}

    @pytest.mark.asyncio
    async def test_exa_web_search_timeout(self, mock_settings):
        """Test handling of timeout from Exa API."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_search("test query")

        assert result == {"results": [], "error": "Request timed out"}

    @pytest.mark.asyncio
    async def test_exa_web_search_no_secret_in_response(self, mock_settings):
        """Test that API key is not exposed in error responses."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
            )

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_search("test query")

        # Ensure the error response doesn't contain the API key
        assert "test-exa-api-key" not in str(result)
        assert "results" in result
        assert "error" in result

    @pytest.mark.asyncio
    async def test_exa_web_fetch_uses_api_key(self, mock_settings):
        """Test that exa_web_fetch reads EXA_API_KEY from configuration."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "results": [{"text": "Page content", "highlights": ["highlight"]}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_fetch("https://example.com")

            mock_client.post.assert_awaited_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-exa-api-key"
            assert call_args[1]["json"]["ids"] == ["https://example.com"]

    @pytest.mark.asyncio
    async def test_exa_web_fetch_missing_api_key(self):
        """Test graceful handling when EXA_API_KEY is missing for fetch."""
        mock_settings = MagicMock()
        mock_settings.EXA_API_KEY = ""

        with patch("app.services.tools.get_settings", return_value=mock_settings):
            result = await exa_web_fetch("https://example.com")

        assert result == {"content": "", "error": "Exa API not configured"}

    @pytest.mark.asyncio
    async def test_exa_web_fetch_no_secret_in_error(self, mock_settings):
        """Test that API key is not exposed in fetch error responses."""
        with patch("app.services.tools.get_settings", return_value=mock_settings):
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock(status_code=401, text="Unauthorized")
            )

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            with patch("app.services.tools.httpx.AsyncClient", return_value=mock_client):
                result = await exa_web_fetch("https://example.com")

        assert "test-exa-api-key" not in str(result)


class TestCalendarTool:
    """Tests for Google Calendar URL generation tool."""

    @pytest.mark.asyncio
    async def test_google_calendar_create_event_valid(self):
        """Test generating a valid Google Calendar event URL."""
        result = await google_calendar_create_event(
            title="Test Event",
            start_datetime="2024-01-15T10:00:00Z",
            end_datetime="2024-01-15T11:00:00Z",
            description="Test description",
            location="Test location",
        )

        assert "url" in result
        assert result["title"] == "Test Event"
        assert result["start"] == "2024-01-15T10:00:00Z"
        assert result["end"] == "2024-01-15T11:00:00Z"
        assert result["description"] == "Test description"
        assert result["location"] == "Test location"
        assert result["url"].startswith("https://calendar.google.com/calendar/render")
        assert "text=Test%20Event" in result["url"]

    @pytest.mark.asyncio
    async def test_google_calendar_invalid_datetime(self):
        """Test handling of invalid datetime format."""
        result = await google_calendar_create_event(
            title="Test",
            start_datetime="invalid-date",
            end_datetime="2024-01-15T11:00:00Z",
        )

        assert "error" in result
        assert "Invalid datetime format" in result["error"]

    @pytest.mark.asyncio
    async def test_google_calendar_end_before_start(self):
        """Test handling when end time is before start time."""
        result = await google_calendar_create_event(
            title="Test",
            start_datetime="2024-01-15T11:00:00Z",
            end_datetime="2024-01-15T10:00:00Z",
        )

        assert "error" in result
        assert "End time must be after start time" in result["error"]


class TestToolRegistry:
    """Tests for the tool registry and execution."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear the tool registry before each test."""
        tool_registry._tools.clear()
        yield
        tool_registry._tools.clear()

    def test_register_and_get_tool(self):
        """Test registering and retrieving a tool."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=AsyncMock(return_value={"result": "success"}),
        )

        tool_registry.register(tool)
        retrieved = tool_registry.get_tool("test_tool")

        assert retrieved is tool

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        retrieved = tool_registry.get_tool("nonexistent")
        assert retrieved is None

    def test_get_tool_definitions(self):
        """Test getting tool definitions in OpenAI format."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"param": {"type": "string"}}},
            handler=AsyncMock(return_value={"result": "success"}),
        )

        tool_registry.register(tool)
        definitions = tool_registry.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0]["type"] == "function"
        assert definitions[0]["function"]["name"] == "test_tool"
        assert definitions[0]["function"]["description"] == "A test tool"
        assert definitions[0]["function"]["parameters"]["properties"]["param"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        mock_handler = AsyncMock(return_value={"result": "success"})

        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={},
            handler=mock_handler,
        )

        tool_registry.register(tool)
        result = await execute_tool("test_tool", {"param": "value"})

        assert result == {"result": "success"}
        mock_handler.assert_awaited_once_with({"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing a tool that doesn't exist."""
        result = await execute_tool("nonexistent", {})

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_error_handling(self):
        """Test error handling during tool execution."""
        mock_handler = AsyncMock(side_effect=Exception("Tool failed"))

        tool = Tool(
            name="failing_tool",
            description="A failing tool",
            parameters={},
            handler=mock_handler,
        )

        tool_registry.register(tool)
        result = await execute_tool("failing_tool", {})

        assert "error" in result
        assert "Tool execution failed" in result["error"]


class TestToolRegistration:
    """Tests for default tool registration."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear the tool registry before each test."""
        tool_registry._tools.clear()
        yield
        tool_registry._tools.clear()

    def test_register_default_tools(self):
        """Test that default tools are registered."""
        register_default_tools()

        assert tool_registry.get_tool("exa_web_search") is not None
        assert tool_registry.get_tool("exa_web_fetch") is not None
        assert tool_registry.get_tool("google_calendar_create_event") is not None

    def test_tool_definitions_format(self):
        """Test that registered tools have correct definition format."""
        register_default_tools()

        definitions = tool_registry.get_tool_definitions()

        assert len(definitions) == 3

        # Check exa_web_search definition
        search_tool = next(d for d in definitions if d["function"]["name"] == "exa_web_search")
        assert search_tool["function"]["name"] == "exa_web_search"
        assert "search" in search_tool["function"]["description"].lower()
        assert "query" in search_tool["function"]["parameters"]["required"]

        # Check exa_web_fetch definition
        fetch_tool = next(d for d in definitions if d["function"]["name"] == "exa_web_fetch")
        assert fetch_tool["function"]["name"] == "exa_web_fetch"
        assert "url" in fetch_tool["function"]["parameters"]["required"]

        # Check google_calendar_create_event definition
        calendar_tool = next(d for d in definitions if d["function"]["name"] == "google_calendar_create_event")
        assert calendar_tool["function"]["name"] == "google_calendar_create_event"
        assert "title" in calendar_tool["function"]["parameters"]["required"]
        assert "start_datetime" in calendar_tool["function"]["parameters"]["required"]
        assert "end_datetime" in calendar_tool["function"]["parameters"]["required"]
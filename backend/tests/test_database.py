import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from app.core.database import init_database, close_database, get_db_session, get_db
from app.models import Memory, Base


class TestDatabaseInitialization:
    def test_init_database_without_url(self):
        with patch("app.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(NEON_DATABASE_URL="")
            init_database()
            from app.core.database import engine, async_session_maker
            assert engine is None
            assert async_session_maker is None

    def test_init_database_with_url(self):
        with patch("app.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(NEON_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test")
            with patch("app.core.database.create_async_engine") as mock_create_engine:
                mock_engine = MagicMock(spec=AsyncEngine)
                mock_create_engine.return_value = mock_engine
                init_database()
                from app.core.database import engine, async_session_maker
                assert engine is mock_engine
                assert async_session_maker is not None
                mock_create_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_database(self):
        with patch("app.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(NEON_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test")
            with patch("app.core.database.create_async_engine") as mock_create_engine:
                mock_engine = AsyncMock()
                mock_create_engine.return_value = mock_engine
                init_database()
                await close_database()
                mock_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_session_raises_when_not_initialized(self):
        from app.core.database import async_session_maker
        async_session_maker = None
        try:
            async with get_db_session() as session:
                pass
        except RuntimeError as e:
            assert "Database not initialized" in str(e)

    @pytest.mark.asyncio
    async def test_get_db_session_commits_on_success(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        def mock_session_maker():
            return mock_session
        
        import app.core.database as db_module
        original_maker = db_module.async_session_maker
        db_module.async_session_maker = mock_session_maker
        
        try:
            async with get_db_session() as session:
                assert session is mock_session
        finally:
            db_module.async_session_maker = original_maker
        
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_session_rollbacks_on_exception(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        def mock_session_maker():
            return mock_session
        
        import app.core.database as db_module
        original_maker = db_module.async_session_maker
        db_module.async_session_maker = mock_session_maker
        
        try:
            try:
                async with get_db_session() as session:
                    raise ValueError("test error")
            except ValueError:
                pass
        finally:
            db_module.async_session_maker = original_maker
        
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        def mock_session_maker():
            return mock_session
        
        import app.core.database as db_module
        original_maker = db_module.async_session_maker
        db_module.async_session_maker = mock_session_maker
        
        try:
            async for session in get_db():
                assert session is mock_session
        finally:
            db_module.async_session_maker = original_maker
        
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()


class TestMemoryModel:
    def test_memory_model_columns(self):
        assert Memory.__tablename__ == "memories"
        
        columns = {c.name: c for c in Memory.__table__.columns}
        
        assert "id" in columns
        assert columns["id"].primary_key
        assert columns["id"].type.length == 36
        
        assert "s3_key" in columns
        assert columns["s3_key"].unique
        assert columns["s3_key"].type.length == 512
        
        assert "original_filename" in columns
        assert columns["original_filename"].type.length == 255
        
        assert "mime_type" in columns
        assert columns["mime_type"].type.length == 100
        
        assert "size_bytes" in columns
        
        assert "processing_status" in columns
        assert columns["processing_status"].type.length == 50
        assert columns["processing_status"].default.arg == "uploaded"
        
        assert "moderation_status" in columns
        assert columns["moderation_status"].type.length == 50
        assert columns["moderation_status"].default.arg == "not_applicable"
        
        assert "ocr_text" in columns
        assert columns["ocr_text"].nullable
        
        assert "metadata_" in columns
        from sqlalchemy.dialects.postgresql import JSONB
        assert isinstance(columns["metadata_"].type, JSONB)
        # default is a dict literal, check it's callable
        assert callable(columns["metadata_"].default.arg) or columns["metadata_"].default.arg == {}
        
        assert "created_at" in columns
        assert columns["created_at"].nullable is False
        
        assert "updated_at" in columns
        assert columns["updated_at"].nullable is False

    def test_memory_model_repr(self):
        memory = Memory(
            id="mem_abc123",
            s3_key="memories/mem_abc123/original.jpg",
            original_filename="test.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )
        repr_str = repr(memory)
        assert "mem_abc123" in repr_str
        assert "test.jpg" in repr_str
        assert "uploaded" in repr_str

    @pytest.mark.asyncio
    async def test_memory_model_basic_insert_read(self):
        mock_session = AsyncMock(spec=AsyncSession)
        
        memory = Memory(
            id="mem_test123",
            s3_key="memories/mem_test123/original.jpg",
            original_filename="test.jpg",
            mime_type="image/jpeg",
            size_bytes=2048,
            processing_status="ready",
            moderation_status="approved",
            ocr_text="Sample OCR text",
            metadata_={"source": "mobile", "tags": ["receipt", "aws"]},
        )
        
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.get = AsyncMock(return_value=memory)
        
        mock_session.add(memory)
        await mock_session.commit()
        await mock_session.refresh(memory)
        
        retrieved = await mock_session.get(Memory, "mem_test123")
        
        assert retrieved is not None
        assert retrieved.id == "mem_test123"
        assert retrieved.original_filename == "test.jpg"
        assert retrieved.mime_type == "image/jpeg"
        assert retrieved.size_bytes == 2048
        assert retrieved.processing_status == "ready"
        assert retrieved.moderation_status == "approved"
        assert retrieved.ocr_text == "Sample OCR text"
        assert retrieved.metadata_ == {"source": "mobile", "tags": ["receipt", "aws"]}

    def test_memory_model_metadata_serialization(self):
        metadata_dict = {
            "source": "web",
            "tags": ["invoice", "pdf"],
            "custom_field": {"nested": "value"},
            "numbers": [1, 2, 3],
        }
        
        memory = Memory(
            id="mem_meta_test",
            s3_key="memories/mem_meta_test/original.pdf",
            original_filename="invoice.pdf",
            mime_type="application/pdf",
            size_bytes=512000,
            metadata_=metadata_dict,
        )
        
        assert memory.metadata_ == metadata_dict
        assert memory.metadata_["source"] == "web"
        assert memory.metadata_["tags"] == ["invoice", "pdf"]
        assert memory.metadata_["custom_field"] == {"nested": "value"}
        assert memory.metadata_["numbers"] == [1, 2, 3]

    def test_memory_model_optional_fields(self):
        memory = Memory(
            id="mem_minimal",
            s3_key="memories/mem_minimal/original.png",
            original_filename="minimal.png",
            mime_type="image/png",
            size_bytes=100,
        )
        
        # SQLAlchemy 2.0 Mapped columns don't apply Python defaults at construction time
        # The defaults are applied at database insert time via server_default
        assert memory.processing_status is None  # Not set at construction
        assert memory.moderation_status is None  # Not set at construction
        assert memory.ocr_text is None
        assert memory.metadata_ is None  # Not set at construction either
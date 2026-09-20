import time
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.models import Memory

logger = get_logger(__name__)


class DatabaseService:
    def __init__(self):
        pass

    async def update_memory_status(
        self,
        db: AsyncSession,
        memory_id: str,
        processing_status: str,
        error_message: Optional[str] = None,
        processing_stage: Optional[str] = None,
    ) -> bool:
        try:
            result = await db.execute(select(Memory).where(Memory.id == memory_id))
            memory = result.scalar_one_or_none()
            if not memory:
                logger.warning("memory_not_found_for_status_update", memory_id=memory_id)
                return False

            memory.processing_status = processing_status
            if processing_stage:
                memory.processing_stage = processing_stage

            await db.flush()

            logger.info(
                "memory_status_updated",
                memory_id=memory_id,
                processing_status=processing_status,
                processing_stage=processing_stage,
            )
            return True
        except Exception as e:
            logger.error("memory_status_update_failed", memory_id=memory_id, error=str(e))
            return False

    async def update_ocr_text(
        self,
        db: AsyncSession,
        memory_id: str,
        ocr_text: Optional[str],
    ) -> bool:
        try:
            result = await db.execute(select(Memory).where(Memory.id == memory_id))
            memory = result.scalar_one_or_none()
            if not memory:
                logger.warning("memory_not_found_for_ocr_update", memory_id=memory_id)
                return False

            memory.ocr_text = ocr_text
            await db.flush()

            logger.info(
                "ocr_text_updated",
                memory_id=memory_id,
                text_length=len(ocr_text) if ocr_text else 0,
            )
            return True
        except Exception as e:
            logger.error("ocr_text_update_failed", memory_id=memory_id, error=str(e))
            return False

    async def get_memory(self, db: AsyncSession, memory_id: str) -> Optional[Memory]:
        try:
            result = await db.execute(select(Memory).where(Memory.id == memory_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("memory_get_failed", memory_id=memory_id, error=str(e))
            return None

    async def get_memories(self, db: AsyncSession) -> List[Memory]:
        try:
            result = await db.execute(select(Memory).order_by(Memory.created_at.desc()))
            return list(result.scalars().all())
        except Exception as e:
            logger.error("memories_get_failed", error=str(e))
            return []

    async def get_memories_by_ids(self, db: AsyncSession, memory_ids: List[str]) -> List[Memory]:
        if not memory_ids:
            return []
        try:
            result = await db.execute(select(Memory).where(Memory.id.in_(memory_ids)))
            return list(result.scalars().all())
        except Exception as e:
            logger.error("memories_get_by_ids_failed", memory_ids=memory_ids, error=str(e))
            return []


database_service = DatabaseService()
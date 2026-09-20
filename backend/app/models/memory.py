from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded", server_default="uploaded")
    processing_stage: Mapped[str | None] = mapped_column(String(50), nullable=True, default="uploaded", server_default="uploaded")
    moderation_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", server_default="pending")
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        status = self.processing_status or "uploaded"
        stage = self.processing_stage or "uploaded"
        return f"<Memory(id={self.id}, filename={self.original_filename}, status={status}, stage={stage})>"
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime


class UploadInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1, max_length=100)
    size_bytes: int = Field(..., gt=0)


class UploadInitResponse(BaseModel):
    memory_id: str
    upload_url: HttpUrl
    s3_key: str
    expires_in: int


class MemoryStatus(BaseModel):
    memory_id: str
    processing_status: str
    moderation_status: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    error_message: Optional[str] = None


class MemoryListItem(BaseModel):
    id: str
    filename: str
    original_filename: str
    mime_type: str
    size: int
    size_bytes: int
    processing_status: str
    moderation_status: str
    s3_key: str
    uploaded_at: Optional[datetime] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    memory_id: str
    score: float
    ocr_text: Optional[str] = None
    s3_key: str
    original_filename: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    timestamp: datetime
    retrieved_memory_ids: List[str] = []


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    answer: str
    sources: List[str]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class QueryResult(BaseModel):
    memory_id: str
    score: float
    ocr_text: Optional[str] = None
    s3_key: str
    original_filename: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[QueryResult]
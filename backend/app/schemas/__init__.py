from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class LogEntryCreate(BaseModel):
    level: str = "info"
    message: str
    source: Optional[str] = "webhook"
    service: Optional[str] = ""
    timestamp: Optional[datetime] = None
    raw_data: Optional[str] = ""
    tags: Optional[str] = ""


class LogEntryResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    source: str
    service: str
    message: str
    tags: str

    class Config:
        from_attributes = True


class LogQueryParams(BaseModel):
    level: Optional[str] = None
    service: Optional[str] = None
    source: Optional[str] = None
    keyword: Optional[str] = None
    regex: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page: int = 1
    page_size: int = 50


class LogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[LogEntryResponse]


class AnalysisResultResponse(BaseModel):
    id: int
    log_id: int
    created_at: datetime
    summary: str
    root_cause: str
    suggestions: str
    severity: str
    model_used: str
    status: str

    class Config:
        from_attributes = True


class WebhookPayload(BaseModel):
    level: Optional[str] = "info"
    message: Optional[str] = ""
    source: Optional[str] = "webhook"
    service: Optional[str] = ""
    logs: Optional[List[dict]] = None
    alerts: Optional[List[dict]] = None


class WebhookConfigCreate(BaseModel):
    name: str
    url: str
    webhook_type: str = "outbound"
    enabled: bool = True
    secret: str = ""


class LLMConfigCreate(BaseModel):
    name: str
    provider: str = "openai_compatible"
    api_base: str
    api_key: str
    model_name: str
    is_default: bool = False


class LLMConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    api_base: str
    model_name: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UploadAnalysisResponse(BaseModel):
    task_id: str
    status: str
    total_lines: int = 0
    error_count: int = 0
    analyses: Optional[List[dict]] = None

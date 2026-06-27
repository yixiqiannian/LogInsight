from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.sql import func
from ..database import Base


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    level = Column(String(20), index=True)
    source = Column(String(100), default="webhook", index=True)
    service = Column(String(100), default="", index=True)
    message = Column(Text)
    raw_data = Column(Text, default="")
    tags = Column(String(500), default="")

    __table_args__ = (
        Index("idx_log_level_time", "level", "timestamp"),
        Index("idx_log_service_time", "service", "timestamp"),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, index=True)
    created_at = Column(DateTime, default=func.now())
    summary = Column(Text)
    root_cause = Column(Text)
    impact_scope = Column(Text, default="")
    suggestions = Column(Text)
    troubleshooting_commands = Column(Text, default="")
    severity = Column(String(20), default="medium")
    context_logs = Column(Text)
    model_used = Column(String(100), default="")
    status = Column(String(20), default="pending")
    incident_id = Column(Integer, default=0)
    is_incremental = Column(Boolean, default=False)
    scenario = Column(String(100), default="")


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    url = Column(String(500))
    webhook_type = Column(String(20), default="outbound")
    enabled = Column(Boolean, default=True)
    secret = Column(String(200), default="")
    push_severity = Column(String(20), default="p1p2")
    created_at = Column(DateTime, default=func.now())


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    provider = Column(String(50), default="openai_compatible")
    api_base = Column(String(500))
    api_key = Column(String(500))
    model_name = Column(String(100))
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_key = Column(String(200), index=True)
    title = Column(String(500), default="")
    severity = Column(String(20), default="medium")
    status = Column(String(20), default="active")
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now())
    log_count = Column(Integer, default=1)
    latest_analysis_id = Column(Integer, default=0)
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, index=True)
    config_value = Column(Text, default="")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

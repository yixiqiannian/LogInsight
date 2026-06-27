import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .log_service import log_service
from ..models import Incident, LogEntry, AnalysisResult, SystemConfig
from ..database import SessionLocal
from ..config import settings

INCIDENT_WINDOW_MINUTES = 30
DEFAULT_AUTO_ANALYZE_LEVEL = "error"


def get_system_config(db: Session, key: str, default: str = "") -> str:
    cfg = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    return cfg.config_value if cfg else default


def set_system_config(db: Session, key: str, value: str):
    cfg = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if cfg:
        cfg.config_value = value
    else:
        cfg = SystemConfig(config_key=key, config_value=value)
        db.add(cfg)
    db.commit()


def should_auto_analyze(level: str, db: Session = None) -> bool:
    if db is None:
        db = SessionLocal()
        try:
            return should_auto_analyze(level, db)
        finally:
            db.close()

    auto_level = get_system_config(db, "auto_analyze_level", DEFAULT_AUTO_ANALYZE_LEVEL).lower()
    level = level.lower()

    if auto_level == "all":
        return True
    if auto_level == "error":
        return level == "error"
    if auto_level == "warn":
        return level in ("error", "warn", "warning")
    if auto_level == "none":
        return False
    return level == "error"


def build_incident_key(log_data: dict) -> str:
    alertname = log_data.get("alertname") or log_data.get("tags", {}).get("alertname") if isinstance(log_data.get("tags"), dict) else None
    service = log_data.get("service", "")
    level = log_data.get("level", "info")

    if alertname:
        return f"alert:{alertname}:{service or 'default'}"

    if service and level in ("error", "warn", "warning"):
        return f"svc:{service}:{level}"

    msg = log_data.get("message", "")[:100]
    return f"log:{level}:{hash(msg) % 10000}"


class IncidentService:
    def find_or_create_incident(self, db: Session, log_data: dict, log_entry: LogEntry = None) -> Incident:
        key = build_incident_key(log_data)
        cutoff = datetime.now() - timedelta(minutes=INCIDENT_WINDOW_MINUTES)

        incident = (
            db.query(Incident)
            .filter(Incident.incident_key == key)
            .filter(Incident.last_seen >= cutoff)
            .filter(Incident.status == "active")
            .order_by(Incident.last_seen.desc())
            .first()
        )

        if incident:
            incident.log_count += 1
            incident.last_seen = datetime.now()
            if log_entry:
                sev = self._level_to_severity(log_entry.level)
                if self._severity_rank(sev) > self._severity_rank(incident.severity):
                    incident.severity = sev
            db.commit()
            db.refresh(incident)
            return incident

        title = log_data.get("message", "")[:100]
        if log_data.get("alertname"):
            title = f"[告警] {log_data['alertname']} - {log_data.get('service', '')}"

        sev = self._level_to_severity(log_data.get("level", "info"))

        incident = Incident(
            incident_key=key,
            title=title,
            severity=sev,
            status="active",
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            log_count=1,
            latest_analysis_id=0,
            summary="",
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        return incident

    def get_incident_context(self, db: Session, incident: Incident, max_logs: int = 30) -> list:
        logs = (
            db.query(LogEntry)
            .filter(LogEntry.timestamp >= incident.first_seen)
            .order_by(LogEntry.timestamp.desc())
            .limit(max_logs)
            .all()
        )
        return list(reversed(logs))

    def get_latest_analysis(self, db: Session, incident: Incident) -> AnalysisResult:
        if not incident or not incident.latest_analysis_id:
            return None
        return db.query(AnalysisResult).filter(AnalysisResult.id == incident.latest_analysis_id).first()

    def update_incident_analysis(self, db: Session, incident_id: int, analysis: AnalysisResult):
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return
        incident.latest_analysis_id = analysis.id
        if analysis.summary:
            incident.summary = analysis.summary[:500]
        if analysis.severity:
            sev_rank = self._severity_rank(analysis.severity)
            cur_rank = self._severity_rank(incident.severity)
            if sev_rank > cur_rank:
                incident.severity = analysis.severity
        db.commit()

    def resolve_incident(self, db: Session, incident_id: int):
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if incident:
            incident.status = "resolved"
            db.commit()

    def _level_to_severity(self, level: str) -> str:
        l = (level or "").lower()
        if l in ("error", "critical", "fatal", "emergency"):
            return "P1"
        if l in ("warn", "warning"):
            return "P3"
        if l in ("info", "notice"):
            return "P4"
        return "P3"

    def _severity_rank(self, sev: str) -> int:
        s = (sev or "").upper()
        if s in ("P1", "CRITICAL", "EMERGENCY"):
            return 4
        if s in ("P2", "HIGH"):
            return 3
        if s in ("P3", "MEDIUM", "WARN", "WARNING"):
            return 2
        if s in ("P4", "LOW", "INFO"):
            return 1
        return 0


incident_service = IncidentService()

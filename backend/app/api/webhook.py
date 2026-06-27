from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import WebhookPayload, WebhookConfigCreate
from ..models import WebhookConfig
from ..services import log_service, ai_service, webhook_service
from ..config import settings

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def _severity_to_level(severity: str) -> str:
    if not severity:
        return "error"
    s = severity.lower()
    if s in ("critical", "fatal", "p1", "emergency"):
        return "error"
    elif s in ("high", "warning", "warn", "p2", "p3"):
        return "warn"
    elif s in ("low", "info", "p4", "ok", "resolved", "normal"):
        return "info"
    return "error"


@router.post("/inbound")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_payload = await request.json()
    source = request.headers.get("X-Webhook-Source", "webhook")

    alerts = raw_payload.get("alerts") or []
    logs = raw_payload.get("logs") or []

    if alerts:
        for alert in alerts:
            labels = alert.get("labels", {}) or {}
            annotations = alert.get("annotations", {}) or {}

            status = alert.get("status", "firing")
            severity = labels.get("severity", labels.get("level", "critical"))
            alertname = labels.get("alertname", "Unknown Alert")

            level = _severity_to_level(severity) if status == "firing" else "info"

            summary = annotations.get("summary", annotations.get("message", ""))
            description = annotations.get("description", annotations.get("details", ""))

            msg_parts = []
            if status == "firing":
                msg_parts.append(f"[告警触发] {alertname}")
            else:
                msg_parts.append(f"[告警恢复] {alertname}")
            if summary:
                msg_parts.append(summary)
            if description:
                msg_parts.append(description)

            message = " - ".join(msg_parts)

            service = labels.get("service", labels.get("app", labels.get("namespace", "")))

            log_data = {
                "level": level,
                "message": message,
                "source": source,
                "service": service,
                "raw_data": str(alert),
            }

            entry = log_service.add_log_sync(db, log_data)
            if level == "error" and settings.AUTO_ANALYZE_ERROR:
                await ai_service.analyze_log(entry.id)

    elif logs:
        for log_item in logs:
            log_data = {
                "level": log_item.get("level", raw_payload.get("level", "info")),
                "message": log_item.get("message", ""),
                "source": log_item.get("source", source),
                "service": log_item.get("service", raw_payload.get("service", "")),
            }
            await log_service.add_log_async(log_data)
            if log_data["level"].lower() == "error" and settings.AUTO_ANALYZE_ERROR:
                entry = log_service.add_log_sync(db, log_data)
                await ai_service.analyze_log(entry.id)

    else:
        log_data = {
            "level": raw_payload.get("level", "info"),
            "message": raw_payload.get("message", ""),
            "source": source,
            "service": raw_payload.get("service", ""),
        }
        await log_service.add_log_async(log_data)
        if log_data["level"].lower() == "error" and settings.AUTO_ANALYZE_ERROR:
            entry = log_service.add_log_sync(db, log_data)
            await ai_service.analyze_log(entry.id)

    return {"status": "received", "alerts_processed": len(alerts), "logs_processed": len(logs)}


@router.get("/configs")
def list_webhook_configs(db: Session = Depends(get_db)):
    configs = db.query(WebhookConfig).all()
    return {"items": configs}


@router.post("/configs")
def create_webhook_config(
    config_data: WebhookConfigCreate,
    db: Session = Depends(get_db),
):
    config = WebhookConfig(**config_data.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/configs/{config_id}")
def delete_webhook_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(WebhookConfig).filter(WebhookConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
    return {"status": "deleted"}


@router.put("/configs/{config_id}")
def update_webhook_config(
    config_id: int,
    config_data: WebhookConfigCreate,
    db: Session = Depends(get_db),
):
    config = db.query(WebhookConfig).filter(WebhookConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    for key, value in config_data.model_dump().items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


@router.post("/test/{config_id}")
async def test_webhook(config_id: int, db: Session = Depends(get_db)):
    config = db.query(WebhookConfig).filter(WebhookConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    success = await webhook_service.send_feishu(
        "LogInsight 测试消息",
        "这是一条来自 LogInsight 的测试消息，Webhook 配置正常工作！",
        config.url,
    )

    return {"success": success}

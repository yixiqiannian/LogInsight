from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import WebhookPayload, WebhookConfigCreate
from ..models import WebhookConfig
from ..services import log_service, ai_service, webhook_service
from ..config import settings

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/inbound")
async def receive_webhook(
    payload: WebhookPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    source = request.headers.get("X-Webhook-Source", "webhook")

    if payload.logs:
        for log_item in payload.logs:
            log_data = {
                "level": log_item.get("level", payload.level),
                "message": log_item.get("message", ""),
                "source": log_item.get("source", source),
                "service": log_item.get("service", payload.service),
            }
            await log_service.add_log_async(log_data)
            if log_data["level"].lower() == "error" and settings.AUTO_ANALYZE_ERROR:
                entry = log_service.add_log_sync(db, log_data)
                await ai_service.analyze_log(entry.id)

    elif payload.alerts:
        for alert in payload.alerts:
            log_data = {
                "level": "error" if alert.get("status") == "firing" else "warn",
                "message": f"[Alert] {alert.get('labels', {}).get('alertname', 'Unknown')}: "
                           f"{alert.get('annotations', {}).get('summary', '')}",
                "source": source,
                "service": alert.get("labels", {}).get("service", payload.service or ""),
                "raw_data": str(alert),
            }
            entry = log_service.add_log_sync(db, log_data)
            if settings.AUTO_ANALYZE_ERROR:
                await ai_service.analyze_log(entry.id)

    else:
        log_data = {
            "level": payload.level or "info",
            "message": payload.message or "",
            "source": source,
            "service": payload.service or "",
        }
        await log_service.add_log_async(log_data)
        if log_data["level"].lower() == "error" and settings.AUTO_ANALYZE_ERROR:
            entry = log_service.add_log_sync(db, log_data)
            await ai_service.analyze_log(entry.id)

    return {"status": "received"}


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

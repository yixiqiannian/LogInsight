from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..schemas import LLMConfigCreate, LLMConfigResponse
from ..models import LLMConfig
from ..services import ai_service

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/llm")
def list_llm_configs(db: Session = Depends(get_db)):
    configs = db.query(LLMConfig).all()
    return {"items": configs}


@router.post("/llm")
def create_llm_config(config_data: LLMConfigCreate, db: Session = Depends(get_db)):
    if config_data.is_default:
        db.query(LLMConfig).filter(LLMConfig.is_default == True).update({"is_default": False})

    config = LLMConfig(**config_data.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)

    if config.is_default:
        ai_service.update_llm_config(config)

    return config


@router.put("/llm/{config_id}")
def update_llm_config(
    config_id: int,
    config_data: LLMConfigCreate,
    db: Session = Depends(get_db),
):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if config_data.is_default:
        db.query(LLMConfig).filter(LLMConfig.id != config_id, LLMConfig.is_default == True).update(
            {"is_default": False}
        )

    for key, value in config_data.model_dump().items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    if config.is_default:
        ai_service.update_llm_config(config)

    return config


@router.delete("/llm/{config_id}")
def delete_llm_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    db.delete(config)
    db.commit()
    return {"status": "deleted"}


@router.post("/llm/{config_id}/set-default")
def set_default_llm(config_id: int, db: Session = Depends(get_db)):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    db.query(LLMConfig).filter(LLMConfig.is_default == True).update({"is_default": False})
    config.is_default = True
    db.commit()

    ai_service.update_llm_config(config)

    return {"status": "default set"}


@router.get("/system")
def get_system_config(db: Session = Depends(get_db)):
    from ..config import settings

    default_llm = db.query(LLMConfig).filter(LLMConfig.is_default == True).first()
    env_configured = bool(settings.LLM_API_KEY and settings.LLM_API_KEY != "your-api-key-here")

    if default_llm:
        llm_info = {
            "api_type": default_llm.api_type,
            "api_base": default_llm.api_base,
            "model_name": default_llm.model_name,
            "configured": True,
            "source": "database",
        }
    elif env_configured:
        llm_info = {
            "api_type": settings.LLM_API_TYPE,
            "api_base": settings.LLM_API_BASE,
            "model_name": settings.LLM_MODEL_NAME,
            "configured": True,
            "source": "env",
        }
    else:
        llm_info = {
            "api_type": settings.LLM_API_TYPE,
            "api_base": settings.LLM_API_BASE,
            "model_name": settings.LLM_MODEL_NAME,
            "configured": False,
            "source": "none",
        }

    return {
        "log_retention": {
            "info_days": settings.LOG_RETENTION_DAYS_INFO,
            "warn_days": settings.LOG_RETENTION_DAYS_WARN,
            "error_days": settings.LOG_RETENTION_DAYS_ERROR,
            "debug_persist": settings.DEBUG_LOG_PERSIST,
        },
        "analysis": {
            "context_window_minutes": settings.CONTEXT_WINDOW_MINUTES,
            "auto_analyze_error": settings.AUTO_ANALYZE_ERROR,
        },
        "llm": llm_info,
    }

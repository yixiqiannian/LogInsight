from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..schemas import AnalysisResultResponse
from ..services import ai_service, log_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/log/{log_id}")
async def analyze_log(
    log_id: int,
    force: bool = Query(False, description="强制重新分析，忽略缓存"),
    db: Session = Depends(get_db),
):
    log_entry = log_service.get_log_by_id(db, log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log not found")

    result = await ai_service.analyze_log(log_id, priority=True, force=force)
    return {
        "log_id": log_id,
        "analysis": result,
    }


@router.get("/log/{log_id}")
def get_analysis_result(log_id: int, db: Session = Depends(get_db)):
    result = ai_service.get_analysis_result(db, log_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    log_entry = log_service.get_log_by_id(db, log_id)
    raw_log = ""
    if log_entry:
        if log_entry.raw_data:
            raw_log = log_entry.raw_data
        else:
            raw_log = log_entry.message or ""

    return {
        "id": result.id,
        "log_id": result.log_id,
        "created_at": result.created_at,
        "summary": result.summary,
        "root_cause": result.root_cause,
        "impact_scope": result.impact_scope,
        "suggestions": result.suggestions,
        "troubleshooting_commands": result.troubleshooting_commands,
        "severity": result.severity,
        "context_logs": result.context_logs,
        "model_used": result.model_used,
        "status": result.status,
        "incident_id": result.incident_id or 0,
        "is_incremental": result.is_incremental or False,
        "scenario": result.scenario or "",
        "raw_log": raw_log,
        "log_message": log_entry.message if log_entry else "",
        "log_level": log_entry.level if log_entry else "",
        "log_service": log_entry.service if log_entry else "",
        "log_source": log_entry.source if log_entry else "",
    }


@router.get("")
def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total, items = ai_service.list_analysis_results(db, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

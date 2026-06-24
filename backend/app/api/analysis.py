from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..schemas import AnalysisResultResponse
from ..services import ai_service, log_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/log/{log_id}")
async def analyze_log(log_id: int, db: Session = Depends(get_db)):
    log_entry = log_service.get_log_by_id(db, log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log not found")

    result = await ai_service.analyze_log(log_id, priority=True)
    return {
        "log_id": log_id,
        "analysis": result,
    }


@router.get("/log/{log_id}")
def get_analysis_result(log_id: int, db: Session = Depends(get_db)):
    result = ai_service.get_analysis_result(db, log_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


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

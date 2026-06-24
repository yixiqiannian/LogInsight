from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..schemas import LogListResponse, LogEntryResponse, LogEntryCreate
from ..services import log_service, filter_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogListResponse)
def get_logs(
    level: Optional[str] = None,
    service: Optional[str] = None,
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    regex: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    total, items = log_service.query_logs(
        db=db,
        level=level,
        service=service,
        source=source,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )

    if regex:
        items = filter_service.filter_by_regex(items, regex)
        total = len(items) + (page - 1) * page_size

    return LogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{log_id}", response_model=LogEntryResponse)
def get_log(log_id: int, db: Session = Depends(get_db)):
    log = log_service.get_log_by_id(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.post("", response_model=LogEntryResponse)
def create_log(log_data: LogEntryCreate, db: Session = Depends(get_db)):
    entry = log_service.add_log_sync(db, log_data.model_dump())
    return entry


@router.get("/{log_id}/context")
def get_log_context(
    log_id: int,
    minutes: int = Query(5, ge=1, le=60),
    db: Session = Depends(get_db),
):
    logs = log_service.get_context_logs(db, log_id, minutes)
    return {
        "log_id": log_id,
        "context_minutes": minutes,
        "total": len(logs),
        "items": logs,
    }

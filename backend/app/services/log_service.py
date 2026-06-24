import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional
from ..models import LogEntry
from ..config import settings
from ..database import SessionLocal


class LogService:
    def __init__(self):
        self._write_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._batch_task = None
        self._sse_clients = []

    async def start_batch_writer(self):
        self._batch_task = asyncio.create_task(self._batch_writer_loop())

    async def stop_batch_writer(self):
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

    async def _batch_writer_loop(self):
        batch = []
        while True:
            try:
                if len(batch) >= settings.BATCH_WRITE_SIZE:
                    self._flush_batch(batch)
                    batch = []
                    continue

                try:
                    item = await asyncio.wait_for(
                        self._write_queue.get(),
                        timeout=settings.BATCH_WRITE_INTERVAL
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    if batch:
                        self._flush_batch(batch)
                        batch = []
            except Exception as e:
                print(f"[LogService] Batch writer error: {e}")
                await asyncio.sleep(1)

    def _flush_batch(self, batch: List[dict]):
        db = SessionLocal()
        try:
            entries = []
            for item in batch:
                if item.get("level", "").lower() == "debug" and not settings.DEBUG_LOG_PERSIST:
                    continue
                entry = LogEntry(
                    timestamp=item.get("timestamp") or datetime.now(),
                    level=item.get("level", "info").lower(),
                    source=item.get("source", "webhook"),
                    service=item.get("service", ""),
                    message=item.get("message", ""),
                    raw_data=item.get("raw_data", ""),
                    tags=item.get("tags", ""),
                )
                entries.append(entry)
            if entries:
                db.bulk_save_objects(entries)
                db.commit()
                self._notify_sse_clients(entries)
        except Exception as e:
            print(f"[LogService] Flush batch error: {e}")
            db.rollback()
        finally:
            db.close()

    def _notify_sse_clients(self, entries: List[LogEntry]):
        for client in self._sse_clients[:]:
            try:
                for entry in entries:
                    client.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    async def add_log_async(self, log_data: dict):
        try:
            self._write_queue.put_nowait(log_data)
        except asyncio.QueueFull:
            pass

    def add_log_sync(self, db: Session, log_data: dict) -> LogEntry:
        entry = LogEntry(
            timestamp=log_data.get("timestamp") or datetime.now(),
            level=log_data.get("level", "info").lower(),
            source=log_data.get("source", "webhook"),
            service=log_data.get("service", ""),
            message=log_data.get("message", ""),
            raw_data=log_data.get("raw_data", ""),
            tags=log_data.get("tags", ""),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def query_logs(
        self,
        db: Session,
        level: Optional[str] = None,
        service: Optional[str] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple:
        query = db.query(LogEntry)

        if level:
            levels = [l.strip().lower() for l in level.split(",") if l.strip()]
            query = query.filter(LogEntry.level.in_(levels))

        if service:
            query = query.filter(LogEntry.service.like(f"%{service}%"))

        if source:
            query = query.filter(LogEntry.source.like(f"%{source}%"))

        if keyword:
            query = query.filter(LogEntry.message.like(f"%{keyword}%"))

        if start_time:
            query = query.filter(LogEntry.timestamp >= start_time)

        if end_time:
            query = query.filter(LogEntry.timestamp <= end_time)

        total = query.count()
        items = (
            query.order_by(desc(LogEntry.timestamp))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return total, items

    def get_context_logs(
        self,
        db: Session,
        log_id: int,
        minutes: int = 5,
    ) -> List[LogEntry]:
        log_entry = db.query(LogEntry).filter(LogEntry.id == log_id).first()
        if not log_entry:
            return []

        start_time = log_entry.timestamp - timedelta(minutes=minutes)
        end_time = log_entry.timestamp + timedelta(minutes=minutes)

        return (
            db.query(LogEntry)
            .filter(
                and_(
                    LogEntry.timestamp >= start_time,
                    LogEntry.timestamp <= end_time,
                )
            )
            .order_by(LogEntry.timestamp.asc())
            .all()
        )

    def get_log_by_id(self, db: Session, log_id: int) -> Optional[LogEntry]:
        return db.query(LogEntry).filter(LogEntry.id == log_id).first()

    def create_sse_client(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=1000)
        self._sse_clients.append(queue)
        return queue

    def remove_sse_client(self, queue: asyncio.Queue):
        if queue in self._sse_clients:
            self._sse_clients.remove(queue)

    def cleanup_old_logs(self, db: Session):
        now = datetime.now()
        levels = {
            "info": settings.LOG_RETENTION_DAYS_INFO,
            "warn": settings.LOG_RETENTION_DAYS_WARN,
            "error": settings.LOG_RETENTION_DAYS_ERROR,
        }
        for level, days in levels.items():
            cutoff = now - timedelta(days=days)
            db.query(LogEntry).filter(
                and_(LogEntry.level == level, LogEntry.timestamp < cutoff)
            ).delete(synchronize_session=False)
        db.commit()


log_service = LogService()

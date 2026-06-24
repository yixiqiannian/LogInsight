import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from datetime import datetime

from ..services import log_service

router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/logs")
async def stream_logs(request: Request):
    queue = log_service.create_sse_client()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    log_entry = await asyncio.wait_for(queue.get(), timeout=1.0)
                    data = json.dumps({
                        "id": log_entry.id,
                        "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else datetime.now().isoformat(),
                        "level": log_entry.level,
                        "source": log_entry.source,
                        "service": log_entry.service,
                        "message": log_entry.message,
                    }, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            log_service.remove_sse_client(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import Base, engine, run_migrations
from app.api import api_router
from app.services import log_service, ai_service
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    await log_service.start_batch_writer()
    await ai_service.start_worker()
    print(f"\n{'='*60}")
    print(f"  LogInsight AI 智能日志分析器")
    print(f"  服务启动: http://{settings.HOST}:{settings.PORT}")
    print(f"  API 文档: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"{'='*60}\n")
    yield
    await log_service.stop_batch_writer()
    await ai_service.stop_worker()


app = FastAPI(
    title="LogInsight API",
    description="AI 智能日志分析器 - 接口文档",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"message": "LogInsight API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )

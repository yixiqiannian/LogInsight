from fastapi import APIRouter
from .logs import router as logs_router
from .webhook import router as webhook_router
from .analysis import router as analysis_router
from .upload import router as upload_router
from .config import router as config_router
from .stream import router as stream_router

api_router = APIRouter()

api_router.include_router(logs_router)
api_router.include_router(webhook_router)
api_router.include_router(analysis_router)
api_router.include_router(upload_router)
api_router.include_router(config_router)
api_router.include_router(stream_router)

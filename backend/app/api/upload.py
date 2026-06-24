from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services import upload_service

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    source: str = "upload",
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unsupported file encoding")

    if len(text_content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    task = await upload_service.analyze_file(file.filename, text_content, source)
    return task


@router.get("/task/{task_id}")
def get_upload_task(task_id: str):
    task = upload_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks")
def list_upload_tasks():
    return {"tasks": upload_service.list_tasks()}

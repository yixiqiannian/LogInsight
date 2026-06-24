import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from .log_service import log_service
from .ai_service import ai_service
from .filter_service import filter_service
from ..database import SessionLocal
from ..models import LogEntry


CHUNK_SIZE = 5000


class UploadService:
    def __init__(self):
        self._tasks = {}

    async def analyze_file(
        self,
        filename: str,
        content: str,
        source: str = "upload",
    ) -> dict:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "filename": filename,
            "status": "processing",
            "total_lines": 0,
            "error_count": 0,
            "warn_count": 0,
            "analyses": [],
            "created_at": datetime.now().isoformat(),
        }

        asyncio.create_task(self._process_file(task_id, filename, content, source))
        return self._tasks[task_id]

    async def _process_file(self, task_id: str, filename: str, content: str, source: str):
        db = SessionLocal()
        try:
            lines = content.splitlines()
            total_lines = len(lines)
            self._tasks[task_id]["total_lines"] = total_lines

            parsed_logs = self._parse_log_lines(lines, filename, source)

            error_logs = filter_service.extract_error_logs(parsed_logs)
            self._tasks[task_id]["error_count"] = len(error_logs)
            self._tasks[task_id]["warn_count"] = sum(
                1 for l in parsed_logs if l.get("level", "").lower() == "warn"
            )

            for log_data in parsed_logs[:1000]:
                log_service.add_log_sync(db, log_data)

            top_errors = error_logs[:5]
            analyses = []

            for err_log in top_errors:
                entry = log_service.add_log_sync(db, err_log)
                result = await ai_service.analyze_log(entry.id, priority=True)
                if result:
                    analyses.append({
                        "log_id": entry.id,
                        "summary": result.summary,
                        "root_cause": result.root_cause,
                        "suggestions": json.loads(result.suggestions) if result.suggestions else [],
                        "severity": result.severity,
                        "message": entry.message,
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    })

            self._tasks[task_id]["analyses"] = analyses

            if total_lines > 1000:
                summary = self._generate_summary(parsed_logs, analyses)
                self._tasks[task_id]["summary"] = summary

            self._tasks[task_id]["status"] = "completed"

        except Exception as e:
            print(f"[UploadService] Process file error: {e}")
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)
        finally:
            db.close()

    def _parse_log_lines(self, lines: List[str], filename: str, source: str) -> List[dict]:
        parsed = []
        for i, line in enumerate(lines):
            if not line.strip():
                continue

            level = "info"
            service = filename
            timestamp = None
            message = line

            lower_line = line.lower()
            if "error" in lower_line or "err" in lower_line or "exception" in lower_line:
                level = "error"
            elif "warn" in lower_line or "warning" in lower_line:
                level = "warn"
            elif "debug" in lower_line:
                level = "debug"

            import re
            time_patterns = [
                r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})",
                r"(\d{2}:\d{2}:\d{2})",
            ]
            for pattern in time_patterns:
                match = re.search(pattern, line)
                if match:
                    time_str = match.group(1)
                    try:
                        if "T" in time_str or "-" in time_str:
                            timestamp = datetime.fromisoformat(time_str.replace("T", " "))
                        else:
                            today = datetime.now().strftime("%Y-%m-%d")
                            timestamp = datetime.fromisoformat(f"{today} {time_str}")
                    except ValueError:
                        pass
                    break

            service_match = re.search(r"\[([a-zA-Z0-9_\-]+)\]", line)
            if service_match:
                service = service_match.group(1)

            parsed.append({
                "timestamp": timestamp,
                "level": level,
                "source": source,
                "service": service,
                "message": message,
                "raw_data": line,
                "tags": f"upload:{filename}",
            })

        return parsed

    def _generate_summary(self, logs: List[dict], analyses: List[dict]) -> dict:
        level_counts = {"error": 0, "warn": 0, "info": 0, "debug": 0}
        services = {}

        for log in logs:
            level = log.get("level", "info").lower()
            level_counts[level] = level_counts.get(level, 0) + 1
            svc = log.get("service", "unknown")
            services[svc] = services.get(svc, 0) + 1

        top_services = sorted(services.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "level_distribution": level_counts,
            "top_services": top_services,
            "total_logs": len(logs),
            "analysis_performed": len(analyses),
        }

    def get_task(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[dict]:
        return list(self._tasks.values())


upload_service = UploadService()

import re
from typing import List, Optional
from ..models import LogEntry


class FilterService:
    def filter_by_level(self, logs: List[LogEntry], levels: List[str]) -> List[LogEntry]:
        level_set = {l.lower() for l in levels}
        return [log for log in logs if log.level.lower() in level_set]

    def filter_by_keyword(self, logs: List[LogEntry], keyword: str) -> List[LogEntry]:
        kw = keyword.lower()
        return [log for log in logs if kw in log.message.lower()]

    def filter_by_regex(self, logs: List[LogEntry], pattern: str) -> List[LogEntry]:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            return [log for log in logs if regex.search(log.message)]
        except re.error:
            return logs

    def filter_by_service(self, logs: List[LogEntry], service: str) -> List[LogEntry]:
        svc = service.lower()
        return [log for log in logs if svc in log.service.lower()]

    def apply_filters(
        self,
        logs: List[LogEntry],
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        regex: Optional[str] = None,
        service: Optional[str] = None,
    ) -> List[LogEntry]:
        result = logs

        if level:
            levels = [l.strip() for l in level.split(",") if l.strip()]
            if levels:
                result = self.filter_by_level(result, levels)

        if service:
            result = self.filter_by_service(result, service)

        if keyword:
            result = self.filter_by_keyword(result, keyword)

        if regex:
            result = self.filter_by_regex(result, regex)

        return result

    def extract_error_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        return [log for log in logs if log.level.lower() == "error"]

    def highlight_keyword(self, message: str, keyword: str) -> str:
        if not keyword:
            return message
        try:
            regex = re.compile(f"({re.escape(keyword)})", re.IGNORECASE)
            return regex.sub(r"<mark>\1</mark>", message)
        except re.error:
            return message


filter_service = FilterService()

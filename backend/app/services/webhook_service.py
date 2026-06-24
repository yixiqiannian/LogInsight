import httpx
import json
from typing import Optional, List
from ..config import settings


class WebhookService:
    async def send_feishu(self, title: str, content: str, webhook_url: Optional[str] = None) -> bool:
        url = webhook_url or settings.FEISHU_WEBHOOK_URL
        if not url:
            return False

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": "red",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    },
                ],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            print(f"[WebhookService] Feishu send error: {e}")
            return False

    async def send_generic(self, webhook_url: str, payload: dict) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            print(f"[WebhookService] Generic send error: {e}")
            return False

    def format_analysis_feishu(self, log_entry, analysis) -> tuple:
        severity_map = {
            "critical": ("🔴 严重", "red"),
            "high": ("🟠 高危", "orange"),
            "medium": ("🟡 中等", "yellow"),
            "low": ("🟢 低危", "green"),
        }
        sev_label, _ = severity_map.get(analysis.severity, ("🟡 中等", "yellow"))

        title = f"[LogInsight] {sev_label} - {analysis.summary[:50]}"

        suggestions_text = ""
        try:
            suggestions = json.loads(analysis.suggestions)
            for i, s in enumerate(suggestions, 1):
                suggestions_text += f"{i}. {s}\n"
        except Exception:
            suggestions_text = analysis.suggestions

        content = f"""
**错误摘要**
{analysis.summary}

**根因分析**
{analysis.root_cause}

**错误日志**
> [{log_entry.level.upper()}] {log_entry.message}

**处理建议**
{suggestions_text}

**模型**: {analysis.model_used}
**时间**: {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()

        return title, content


webhook_service = WebhookService()

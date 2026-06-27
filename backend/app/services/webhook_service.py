import httpx
import json
from typing import Optional, List
from sqlalchemy.orm import Session
from ..config import settings
from ..models import WebhookConfig, AnalysisResult, LogEntry


def _should_push(severity: str, push_config: str) -> bool:
    if not push_config or push_config == "all":
        return True
    s = severity.upper()
    p = push_config.lower()
    if p == "p1p2":
        return s in ("P1", "P2", "CRITICAL", "HIGH")
    elif p == "p1":
        return s in ("P1", "CRITICAL")
    elif p == "none":
        return False
    return True


class WebhookService:
    async def push_analysis_result(self, db: Session, log_entry: LogEntry, analysis: AnalysisResult):
        configs = db.query(WebhookConfig).filter(WebhookConfig.enabled == True).all()
        if not configs:
            return

        title, content = self.format_analysis_feishu(log_entry, analysis)

        for config in configs:
            try:
                if not _should_push(analysis.severity, config.push_severity or "p1p2"):
                    continue

                if config.webhook_type == "feishu" or config.webhook_type == "lark":
                    await self.send_feishu(title, content, config.url)
                elif config.webhook_type == "dingtalk":
                    await self._send_dingtalk(title, content, config.url)
                elif config.webhook_type == "slack":
                    await self._send_slack(title, content, config.url)
                else:
                    await self.send_generic(config.url, {
                        "title": title,
                        "content": content,
                        "severity": analysis.severity,
                        "summary": analysis.summary,
                        "log_id": analysis.log_id,
                    })
                print(f"[WebhookService] Pushed analysis result to {config.name}")
            except Exception as e:
                print(f"[WebhookService] Push to {config.name} failed: {e}")

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

    async def _send_dingtalk(self, title: str, content: str, webhook_url: str) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            print(f"[WebhookService] DingTalk send error: {e}")
            return False

    async def _send_slack(self, title: str, content: str, webhook_url: str) -> bool:
        payload = {
            "text": title,
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": content}},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            print(f"[WebhookService] Slack send error: {e}")
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
        sev = analysis.severity or "medium"
        s = sev.upper()

        if s in ("P1", "CRITICAL", "EMERGENCY"):
            sev_label = "🔴 P1 紧急"
            template = "red"
        elif s in ("P2", "HIGH"):
            sev_label = "🟠 P2 高危"
            template = "orange"
        elif s in ("P3", "MEDIUM"):
            sev_label = "🟡 P3 中等"
            template = "yellow"
        elif s in ("P4", "LOW", "INFO"):
            sev_label = "🟢 P4 低危"
            template = "green"
        else:
            sev_label = f"🟡 {sev.upper()}"
            template = "yellow"

        title = f"[LogInsight] {sev_label} - {(analysis.summary or '')[:50]}"

        suggestions_text = ""
        try:
            suggestions = json.loads(analysis.suggestions)
            if isinstance(suggestions, list):
                for i, s_item in enumerate(suggestions, 1):
                    suggestions_text += f"{i}. {s_item}\n"
            else:
                suggestions_text = analysis.suggestions
        except Exception:
            suggestions_text = analysis.suggestions or ""

        impact_scope = analysis.impact_scope or ""
        troubleshooting = analysis.troubleshooting_commands or ""
        scenario = getattr(analysis, "scenario", "") or ""
        is_incr = getattr(analysis, "is_incremental", False)

        content_parts = []

        if scenario or is_incr:
            tags = []
            if scenario:
                tags.append(f"🏷️ {scenario[:40]}")
            if is_incr:
                tags.append("📈 增量分析")
            content_parts.append("  ".join(tags))
            content_parts.append("")

        content_parts.append("**错误摘要**")
        content_parts.append(analysis.summary or "未知")
        content_parts.append("")

        content_parts.append("**根因分析**")
        content_parts.append((analysis.root_cause or "")[:500])
        content_parts.append("")

        if impact_scope and impact_scope.strip():
            content_parts.append("**影响范围**")
            content_parts.append(impact_scope[:300])
            content_parts.append("")

        content_parts.append("**错误日志**")
        content_parts.append(f"> [{(log_entry.level or '').upper()}] {log_entry.message}")
        content_parts.append("")

        if suggestions_text and suggestions_text.strip():
            content_parts.append("**处理建议**")
            content_parts.append(suggestions_text.strip())
            content_parts.append("")

        if troubleshooting and troubleshooting.strip():
            content_parts.append("**排障命令**")
            content_parts.append(troubleshooting[:400])
            content_parts.append("")

        content_parts.append(f"**模型**: {analysis.model_used or 'unknown'}")
        content_parts.append(f"**时间**: {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        content = "\n".join(content_parts).strip()

        return title, content


webhook_service = WebhookService()

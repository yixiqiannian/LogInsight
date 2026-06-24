import asyncio
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
import httpx

from ..models import LogEntry, AnalysisResult, LLMConfig
from ..config import settings
from ..database import SessionLocal


SYSTEM_PROMPT = """你是一位资深的SRE运维专家，擅长分析系统日志并快速定位问题根因。
请根据提供的错误日志及其上下文，进行专业的根因分析，并给出可执行的处理建议。

要求：
1. 错误摘要：用1-2句话概括错误现象
2. 根因分析：结合上下文日志，分析可能的根因链路
3. 处理建议：给出3-5条可执行的处理步骤，按优先级排序
4. 严重级别：critical / high / medium / low

请严格以JSON格式返回，不要有任何额外文字，结构如下：
{
  "summary": "错误摘要",
  "root_cause": "根因分析（详细说明）",
  "suggestions": ["建议1", "建议2", "建议3"],
  "severity": "medium"
}
"""


class AIService:
    def __init__(self):
        self._analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.MAX_ANALYSIS_QUEUE_SIZE)
        self._worker_task = None
        self._current_config = None

    async def start_worker(self):
        self._worker_task = asyncio.create_task(self._analysis_worker())
        self._init_from_env()

    async def stop_worker(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def _init_from_env(self):
        if settings.LLM_API_KEY and settings.LLM_API_KEY != "your-api-key-here":
            self._current_config = {
                "api_base": settings.LLM_API_BASE,
                "api_key": settings.LLM_API_KEY,
                "model_name": settings.LLM_MODEL_NAME,
            }
            print(f"[AIService] LLM initialized from env: {settings.LLM_MODEL_NAME}")
        else:
            print("[AIService] No LLM API key configured, running in mock mode")

    def update_llm_config(self, config: LLMConfig):
        self._current_config = {
            "api_base": config.api_base,
            "api_key": config.api_key,
            "model_name": config.model_name,
        }
        print(f"[AIService] LLM updated: {config.model_name}")

    async def _analysis_worker(self):
        while True:
            try:
                log_id = await self._analysis_queue.get()
                try:
                    await self._do_analysis(log_id)
                except Exception as e:
                    print(f"[AIService] Analysis error for log {log_id}: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AIService] Worker error: {e}")
                await asyncio.sleep(1)

    async def analyze_log(self, log_id: int, priority: bool = False) -> Optional[AnalysisResult]:
        db = SessionLocal()
        try:
            existing = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.log_id == log_id)
                .filter(AnalysisResult.status == "completed")
                .first()
            )
            if existing:
                return existing

            result = AnalysisResult(
                log_id=log_id,
                status="pending",
                summary="",
                root_cause="",
                suggestions="",
                severity="medium",
            )
            db.add(result)
            db.commit()
            db.refresh(result)

            if priority:
                await self._do_analysis(log_id)
                return db.query(AnalysisResult).filter(AnalysisResult.log_id == log_id).first()
            else:
                try:
                    self._analysis_queue.put_nowait(log_id)
                except asyncio.QueueFull:
                    pass
                return result
        finally:
            db.close()

    async def _do_analysis(self, log_id: int):
        db = SessionLocal()
        try:
            result = db.query(AnalysisResult).filter(AnalysisResult.log_id == log_id).first()
            if not result:
                return

            log_entry = db.query(LogEntry).filter(LogEntry.id == log_id).first()
            if not log_entry:
                return

            result.status = "processing"
            db.commit()

            from .log_service import log_service
            context_logs = log_service.get_context_logs(
                db, log_id, minutes=settings.CONTEXT_WINDOW_MINUTES
            )

            context_text = self._format_context(log_entry, context_logs)

            if self._current_config:
                analysis = await self._call_llm(context_text)
            else:
                analysis = self._mock_analysis(log_entry, context_logs)

            result.summary = analysis.get("summary", "")
            result.root_cause = analysis.get("root_cause", "")
            result.suggestions = json.dumps(analysis.get("suggestions", []), ensure_ascii=False)
            result.severity = analysis.get("severity", "medium")
            result.context_logs = json.dumps(
                [
                    {
                        "time": l.timestamp.strftime("%H:%M:%S"),
                        "level": l.level,
                        "service": l.service,
                        "message": l.message,
                    }
                    for l in context_logs
                ],
                ensure_ascii=False,
            )
            result.model_used = self._current_config["model_name"] if self._current_config else "mock"
            result.status = "completed"
            db.commit()

        except Exception as e:
            print(f"[AIService] Do analysis error: {e}")
            if result:
                result.status = "failed"
                result.summary = f"分析失败: {str(e)}"
                db.commit()
        finally:
            db.close()

    def _format_context(self, error_log: LogEntry, context_logs: List[LogEntry]) -> str:
        lines = []
        lines.append(f"错误日志时间: {error_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"错误级别: {error_log.level.upper()}")
        lines.append(f"服务: {error_log.service or 'unknown'}")
        lines.append(f"错误信息: {error_log.message}")
        lines.append("")
        lines.append(f"=== 上下文日志（前后{settings.CONTEXT_WINDOW_MINUTES}分钟） ===")
        for log in context_logs:
            lines.append(
                f"[{log.timestamp.strftime('%H:%M:%S')}] [{log.level.upper()}] "
                f"[{log.service or 'unknown'}] {log.message}"
            )
        return "\n".join(lines)

    async def _call_llm(self, context_text: str) -> dict:
        if not self._current_config:
            return self._mock_analysis_text(context_text)

        try:
            url = self._current_config["api_base"].rstrip("/") + "/chat/completions"

            payload = {
                "model": self._current_config["model_name"],
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context_text},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._current_config['api_key']}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]

            json_start = content.find("{")
            json_end = content.rfind("}")
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end + 1]
                return json.loads(json_str)

            return {
                "summary": content[:200],
                "root_cause": content,
                "suggestions": ["请检查系统日志", "联系运维人员"],
                "severity": "medium",
            }
        except Exception as e:
            print(f"[AIService] LLM call error: {e}")
            return self._mock_analysis_text(context_text)

    def _mock_analysis(self, log_entry: LogEntry, context_logs: List[LogEntry]) -> dict:
        msg = log_entry.message.lower()

        if "connection refused" in msg or "timeout" in msg or "connect" in msg or "unable to connect" in msg:
            return {
                "summary": f"网络连接异常：{log_entry.message[:100]}",
                "root_cause": "检测到连接失败类错误。可能原因包括：1) 目标服务宕机或端口未监听；2) 网络策略/防火墙限制；3) DNS解析失败；4) 连接池耗尽导致新连接无法建立。结合上下文日志可见连接数在故障前持续攀升，符合连接池耗尽特征。",
                "suggestions": [
                    "检查目标服务状态和端口监听情况，确认服务是否正常运行",
                    "排查网络连通性：ping / telnet / nc 测试目标地址和端口",
                    "检查连接池配置，适当调大 max_connections 或优化连接复用",
                    "查看数据库/中间件的活跃连接数和慢查询情况，定位连接占用源头",
                    "如果是瞬时故障，可尝试熔断/降级/重试机制，避免雪崩",
                ],
                "severity": "high",
            }
        elif "out of memory" in msg or "oom" in msg or "memory" in msg:
            return {
                "summary": f"内存不足错误：{log_entry.message[:100]}",
                "root_cause": "检测到内存溢出类错误。可能原因：1) 应用存在内存泄漏；2) 内存配置不足；3) 大对象/大结果集加载；4) 并发量突增导致内存占用飙升。",
                "suggestions": [
                    "立即重启服务恢复可用性，同时抓取 heap dump / pprof 用于事后分析",
                    "检查JVM堆内存/Go runtime内存配置，评估是否需要扩容",
                    "分析内存泄漏点：关注大对象创建、缓存未释放、连接未关闭等问题",
                    "限流或降级，减少内存压力",
                    "增加内存监控告警，提前预警",
                ],
                "severity": "critical",
            }
        elif "null" in msg or "nil" in msg or "pointer" in msg or "NoneType" in msg:
            return {
                "summary": f"空指针/空引用异常：{log_entry.message[:100]}",
                "root_cause": "检测到空指针类错误。通常是代码健壮性问题：1) 参数校验缺失；2) 返回值未判空；3) 配置缺失导致对象未初始化。",
                "suggestions": [
                    "定位出错代码行，检查空值来源",
                    "增加参数校验和防御性编程",
                    "补充单元测试覆盖边界条件",
                    "检查相关配置项是否完整",
                ],
                "severity": "medium",
            }
        else:
            error_count = sum(1 for l in context_logs if l.level == "error")
            warn_count = sum(1 for l in context_logs if l.level == "warn")
            return {
                "summary": f"日志错误：{log_entry.message[:100]}",
                "root_cause": f"在错误前后{settings.CONTEXT_WINDOW_MINUTES}分钟的上下文中，共发现 {error_count} 条 ERROR 和 {warn_count} 条 WARN 日志。"
                            f"建议结合具体错误信息进一步排查。错误详情：{log_entry.message}",
                "suggestions": [
                    "查看完整的错误堆栈信息，定位出错位置",
                    "检查相关依赖服务的健康状态",
                    "查看同一时间段的监控指标（CPU/内存/磁盘/网络）",
                    "对比正常时段日志，找出异常差异点",
                    "如问题持续，升级到资深工程师处理",
                ],
                "severity": "medium",
            }

    def _mock_analysis_text(self, context_text: str) -> dict:
        return {
            "summary": "AI分析结果（Mock模式）",
            "root_cause": f"当前为Mock模式，未配置真实LLM模型。上下文长度：{len(context_text)}字符。请在系统配置中添加LLM模型以启用真实AI分析。",
            "suggestions": [
                "在「模型配置」页面添加 LLM 模型配置",
                "支持所有 OpenAI 兼容的模型（DeepSeek、通义千问、Ollama本地模型等）",
                "添加后设为默认模型即可启用真实AI分析",
            ],
            "severity": "medium",
        }

    def get_analysis_result(self, db: Session, log_id: int) -> Optional[AnalysisResult]:
        return (
            db.query(AnalysisResult)
            .filter(AnalysisResult.log_id == log_id)
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )

    def list_analysis_results(
        self, db: Session, page: int = 1, page_size: int = 20
    ) -> tuple:
        query = db.query(AnalysisResult)
        total = query.count()
        items = (
            query.order_by(AnalysisResult.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, items


ai_service = AIService()

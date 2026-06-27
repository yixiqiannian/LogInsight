import asyncio
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
import httpx

from ..models import LogEntry, AnalysisResult, LLMConfig
from ..config import settings
from ..database import SessionLocal


SYSTEM_PROMPT = """你是一名拥有15年以上经验的全栈运维与 AIOps 专家，精通 Kubernetes、Nginx、Linux 系统、数据库、中间件、网络、应用服务等各类运维场景，所有回答必须使用中文。

请先仔细阅读提供的错误日志及上下文，**首先判断故障所属的场景类型**，然后再进行专业分析。

【场景识别规则】
从日志内容、服务名、错误关键字中判断场景：
- Kubernetes 场景：日志中包含 kubectl、pod、namespace、node、kubelet、apiserver、calico、CrashLoopBackOff、ImagePullBackOff 等 K8s 关键词
- Nginx 场景：日志中包含 nginx、upstream、proxy_pass、502/504、connection refused、upstream timeout 等关键词
- Linux 系统场景：日志中包含 systemd、OOM、out of memory、disk full、no space left、CPU、kernel、pan 等关键词
- 数据库场景：日志中包含 mysql、postgres、redis、mongodb、SQL、connection refused、deadlock、timeout 等数据库关键词
- 中间件场景：日志中包含 kafka、rabbitmq、elasticsearch、redis 等中间件关键词
- 应用服务场景：Java/Python/Node.js 应用报错，包含 Exception、Traceback、NullPointerException、stack 等
- 网络场景：日志中包含 timeout、connection refused、DNS、TLS、SSL、certificate 等网络相关错误
- 混合/不确定：多种关键词都有或无法明确判断

【输出格式要求】
严格按照以下6个部分输出，每个部分用明确的标记开头：

【错误摘要】
（用一句话概括错误现象和影响）

【场景分类】
（从上面的场景分类中选择1-2个最匹配的，并说明判断依据：哪些关键词或特征让你判断属于这个场景）

【根因分析】
（结合上下文日志，推理出完整的故障根因链路，要有分析过程，列出最可能的2-3个根因，按可能性排序）

【影响范围】
（影响的服务、组件、系统、用户，对业务的影响，可能扩散的风险）

【严重等级】
（P1 紧急 / P2 高 / P3 中 / P4 低，并说明判断依据）

【处理建议】
1. （第一条建议）
2. （第二条建议）
3. （第三条建议）
4. （第四条建议）
5. （第五条建议）
（按优先级从高到低排序，优先给出紧急止血方案，再给根因修复方案。建议要匹配对应场景，不要给 K8s 建议去解决纯 Nginx 问题）

【排障命令】
（提供 8-15 条具体的排查命令，放在 ```bash ... ``` 代码块中。
**重要：命令必须匹配场景类型！**
- 如果是 K8s 场景：用 kubectl 命令，从上下文中提取 namespace、pod名、node名填入
- 如果是 Nginx 场景：用 nginx -t、nginx -s reload、tail /var/log/nginx/error.log、curl 测试、检查 upstream 等
- 如果是 Linux 系统场景：用 top、df -h、free -m、dmesg、journalctl、systemctl status 等
- 如果是数据库场景：用对应数据库的连接命令、查看慢查询、检查连接数等
- 如果是混合/不确定场景：先给通用的 Linux/网络排查命令，再根据日志线索给针对性命令
命令按排查思路顺序排列：先看状态→再看日志→深入排查。
命令中涉及的主机名、路径要符合场景，不要凭空编造 K8s 资源名。）

【重要提醒】
- 所有内容必须是中文
- 严格按照上面的标记输出，不要改变标记文字
- 每个部分内容要充实、专业、可执行
- 排障命令必须放在 ```bash ... ``` 代码块里
- **绝对不要在非 K8s 场景下给出 kubectl 命令！**
- 场景判断要准确，建议和命令都要与场景匹配
"""

INCREMENTAL_PROMPT = """你是一名拥有15年以上经验的全栈运维与 AIOps 专家，精通 Kubernetes、Nginx、Linux 系统、数据库、中间件、网络等各类运维场景，所有回答必须使用中文。

这是一次**增量分析**：同一故障事件有新的日志补充，上一次分析结论如下：

【上一次分析摘要】
{previous_summary}

【上一次根因分析】
{previous_root_cause}

【上一次处理建议】
{previous_suggestions}

【上一次严重等级】
{previous_severity}

====================
【新的日志及上下文】
{context}
====================

请先判断故障所属的场景类型（K8s / Nginx / Linux / 数据库 / 中间件 / 应用 / 网络 / 混合），然后基于上一次的分析结论，结合新补充的日志进行**增量更新分析**：
- 如果新日志确认了之前的判断，给出确认说明
- 如果新日志发现了新的线索或根因变化，更新分析结论
- 如果严重等级有变化，说明变化原因
- 处理建议根据新情况更新，保留仍然有效的建议

【输出格式要求】
严格按照以下6个部分输出，每个部分用明确的标记开头：

【错误摘要】
（更新后的错误摘要）

【场景分类】
（场景类型及判断依据，如有变化说明原因）

【根因分析】
（更新后的根因分析，说明相比上次有哪些新发现或变化）

【影响范围】
（更新后的影响范围）

【严重等级】
（P1 紧急 / P2 高 / P3 中 / P4 低，如有变化说明原因）

【处理建议】
1. （第一条建议）
2. （第二条建议）
3. （第三条建议）
4. （第四条建议）
5. （第五条建议）
（按优先级排序，保留有效建议，新增新建议。建议要匹配场景类型）

【排障命令】
（更新后的排障命令，放在 ```bash ... ``` 代码块中。
命令必须匹配场景类型，非 K8s 场景不要给 kubectl 命令。）

【重要提醒】
- 所有内容必须是中文
- 严格按照上面的标记输出
- 要体现增量分析的特点，说明与上次分析的差异
- 排障命令必须放在 ```bash ... ``` 代码块里
- **绝对不要在非 K8s 场景下给出 kubectl 命令！**
"""


class AIService:
    def __init__(self):
        self._analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.MAX_ANALYSIS_QUEUE_SIZE)
        self._worker_task = None
        self._current_config = None

    async def start_worker(self):
        self._worker_task = asyncio.create_task(self._analysis_worker())
        self._init_from_env()
        if not self._current_config:
            self._init_from_db()

    def _init_from_db(self):
        db = SessionLocal()
        try:
            default_config = db.query(LLMConfig).filter(LLMConfig.is_default == True).first()
            if default_config:
                self._current_config = {
                    "api_base": default_config.api_base,
                    "api_key": default_config.api_key,
                    "model_name": default_config.model_name,
                }
                print(f"[AIService] LLM initialized from db: {default_config.model_name}")
        except Exception as e:
            print(f"[AIService] Failed to init LLM from db: {e}")
        finally:
            db.close()

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

    async def analyze_log(self, log_id: int, priority: bool = False, force: bool = False) -> Optional[AnalysisResult]:
        db = SessionLocal()
        try:
            existing = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.log_id == log_id)
                .filter(AnalysisResult.status == "completed")
                .first()
            )
            if existing and not force:
                return existing

            if force and existing:
                db.delete(existing)
                db.commit()

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
                db.expire_all()
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
        result = None
        try:
            result = db.query(AnalysisResult).filter(AnalysisResult.log_id == log_id).first()
            if not result:
                return

            log_entry = db.query(LogEntry).filter(LogEntry.id == log_id).first()
            if not log_entry:
                return

            result.status = "processing"
            db.commit()

            if not self._current_config:
                default_config = db.query(LLMConfig).filter(LLMConfig.is_default == True).first()
                if default_config:
                    self._current_config = {
                        "api_base": default_config.api_base,
                        "api_key": default_config.api_key,
                        "model_name": default_config.model_name,
                    }
                    print(f"[AIService] LLM loaded from db: {default_config.model_name}")

            from .incident_service import incident_service
            log_data = {
                "level": log_entry.level,
                "message": log_entry.message,
                "service": log_entry.service,
                "source": log_entry.source,
            }
            incident = incident_service.find_or_create_incident(db, log_data, log_entry)
            result.incident_id = incident.id

            previous_analysis = incident_service.get_latest_analysis(db, incident)
            is_incremental = previous_analysis is not None and incident.log_count > 1
            result.is_incremental = is_incremental

            from .log_service import log_service
            context_logs = log_service.get_context_logs(
                db, log_id, minutes=settings.CONTEXT_WINDOW_MINUTES
            )

            if self._current_config:
                if is_incremental:
                    context_text = self._format_context(log_entry, context_logs)
                    analysis = await self._call_llm_incremental(previous_analysis, context_text)
                    print(f"[AIService] Incremental analysis for incident {incident.id}, log #{incident.log_count}")
                else:
                    context_text = self._format_context(log_entry, context_logs)
                    analysis = await self._call_llm(context_text)
            else:
                analysis = self._mock_analysis(log_entry, context_logs)

            result.summary = analysis.get("summary", "")
            result.root_cause = analysis.get("root_cause", "")
            result.impact_scope = analysis.get("impact_scope", "")
            result.suggestions = json.dumps(analysis.get("suggestions", []), ensure_ascii=False)
            result.troubleshooting_commands = analysis.get("troubleshooting_commands", "")
            result.severity = analysis.get("severity", "medium")
            result.scenario = analysis.get("scenario", "")[:100]
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
            db.refresh(result)

            try:
                incident_service.update_incident_analysis(db, incident.id, result)
            except Exception as inc_err:
                print(f"[AIService] Update incident error: {inc_err}")

            try:
                from .webhook_service import webhook_service
                await webhook_service.push_analysis_result(db, log_entry, result)
            except Exception as push_err:
                print(f"[AIService] Push analysis result error: {push_err}")

        except Exception as e:
            print(f"[AIService] Do analysis error: {e}")
            if result:
                result.status = "failed"
                result.summary = f"分析失败: {str(e)}"
                db.commit()
        finally:
            db.close()

    def _normalize_result(self, result: dict) -> dict:
        if not isinstance(result, dict):
            return result
        result.setdefault("summary", "")
        result.setdefault("root_cause", "")
        result.setdefault("impact_scope", "")
        result.setdefault("scenario", "")
        result.setdefault("severity", "medium")
        result.setdefault("suggestions", [])
        result.setdefault("troubleshooting_commands", "")

        import re

        def _clean_section_markers(text: str) -> str:
            if not text:
                return text
            text = text.strip()
            text = re.sub(r"^【[^】]+】\s*", "", text)
            text = re.sub(r"^[^\n：:]+[：:]\s*", "", text, count=1)
            return text.strip()

        result["summary"] = _clean_section_markers(result["summary"])
        result["root_cause"] = _clean_section_markers(result["root_cause"])
        result["impact_scope"] = _clean_section_markers(result["impact_scope"])
        result["scenario"] = _clean_section_markers(result["scenario"])

        sev_val = str(result.get("severity", "")).strip().upper()
        if "P1" in sev_val or "紧急" in sev_val or "CRITICAL" in sev_val:
            result["severity"] = "P1"
        elif "P2" in sev_val or "高" in sev_val or "HIGH" in sev_val:
            result["severity"] = "P2"
        elif "P3" in sev_val or "中" in sev_val or "MEDIUM" in sev_val:
            result["severity"] = "P3"
        elif "P4" in sev_val or "低" in sev_val or "LOW" in sev_val:
            result["severity"] = "P4"
        else:
            result["severity"] = "P3"

        if isinstance(result["suggestions"], str):
            sug_text = result["suggestions"].strip()
            sug_text = _clean_section_markers(sug_text)
            lines = []
            for line in sug_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                m2 = re.match(r"^(\d+[.、]|\-)\s*(.+)", line)
                if m2:
                    lines.append(m2.group(2).strip())
                elif lines:
                    lines[-1] += "\n" + line
                elif len(lines) < 1:
                    lines.append(line)
            result["suggestions"] = lines[:8]

        if not isinstance(result["suggestions"], list):
            result["suggestions"] = []

        result["suggestions"] = [_clean_section_markers(s) for s in result["suggestions"] if s and s.strip()]

        result["troubleshooting_commands"] = _clean_section_markers(result["troubleshooting_commands"])
        cmd_text = result["troubleshooting_commands"]
        if cmd_text and "```bash" not in cmd_text and "```" in cmd_text:
            cmd_text = "```bash\n" + cmd_text.replace("```", "") + "\n```"
            result["troubleshooting_commands"] = cmd_text
        elif cmd_text and "```" not in cmd_text:
            cmd_text = "```bash\n" + cmd_text + "\n```"
            result["troubleshooting_commands"] = cmd_text

        return result

    def _extract_from_text(self, text: str) -> dict:
        import re
        result = {
            "summary": "",
            "root_cause": "",
            "impact_scope": "",
            "severity": "medium",
            "suggestions": [],
            "troubleshooting_commands": "",
        }

        text = text.strip()

        # 如果看起来是 JSON，先尝试解析 JSON
        if text.startswith("{") or text.startswith("```"):
            json_text = re.sub(r"^```(?:json)?\s*", "", text)
            json_text = re.sub(r"\n?```\s*$", "", json_text)
            json_text = json_text.strip()
            if json_text.startswith("{"):
                try:
                    parsed = json.loads(json_text)
                    if isinstance(parsed, dict) and ("summary" in parsed or "root_cause" in parsed):
                        normalized = self._normalize_result(parsed)
                        if normalized.get("summary") or normalized.get("root_cause"):
                            return normalized
                except json.JSONDecodeError:
                    pass

        # 去掉 markdown 代码块包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        # 提取错误摘要
        patterns = [
            r"【错误摘要】\s*(.+?)(?=\n【|$)",
            r"错误摘要[：:]\s*(.+?)(?=\n\n|\n【|$)",
            r"摘要[：:]\s*(.+?)(?=\n\n|\n【|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                val = m.group(1).strip()
                val = re.sub(r"^\d+[.、]\s*", "", val)
                result["summary"] = val[:200]
                break

        # 提取根因分析
        patterns = [
            r"【根因分析】\s*(.+?)(?=\n【|$)",
            r"根因分析[：:]\s*(.+?)(?=\n【|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                result["root_cause"] = m.group(1).strip()
                break

        # 提取影响范围
        patterns = [
            r"【影响范围】\s*(.+?)(?=\n【|$)",
            r"影响范围[：:]\s*(.+?)(?=\n【|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                result["impact_scope"] = m.group(1).strip()
                break

        # 提取场景分类
        patterns = [
            r"【场景分类】\s*(.+?)(?=\n【|$)",
            r"场景分类[：:]\s*(.+?)(?=\n【|$)",
            r"场景[：:]\s*(.+?)(?=\n【|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                result["scenario"] = m.group(1).strip()[:100]
                break

        # 提取严重等级
        patterns = [
            r"【严重等级】\s*(.+?)(?=\n【|$)",
            r"严重等级[：:]\s*(.+?)(?=\n【|$)",
            r"严重级别[：:]\s*(.+?)(?=\n【|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                val = m.group(1).strip().upper()
                if "P1" in val or "紧急" in val or "CRITICAL" in val:
                    result["severity"] = "P1"
                elif "P2" in val or "高" in val or "HIGH" in val:
                    result["severity"] = "P2"
                elif "P3" in val or "中" in val or "MEDIUM" in val:
                    result["severity"] = "P3"
                elif "P4" in val or "低" in val or "LOW" in val:
                    result["severity"] = "P4"
                break

        # 提取处理建议
        patterns = [
            r"【处理建议】\s*(.+?)(?=\n【|$)",
            r"处理建议[：:]\s*(.+?)(?=\n【|$)",
            r"建议[：:]\s*(.+?)(?=\n【|$)",
        ]
        sug_text = ""
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                sug_text = m.group(1).strip()
                break

        if sug_text:
            lines = []
            for line in sug_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                m2 = re.match(r"^(\d+[.、]|\-)\s*(.+)", line)
                if m2:
                    lines.append(m2.group(2).strip())
                elif lines:
                    lines[-1] += "\n" + line
                elif len(lines) < 1:
                    lines.append(line)
            result["suggestions"] = lines[:8]

        # 提取排障命令
        patterns = [
            r"【排障命令】\s*(.+?)(?=\n【|$)",
            r"排障命令[：:]\s*(.+?)(?=\n【|$)",
            r"排查命令[：:]\s*(.+?)(?=\n【|$)",
        ]
        cmd_text = ""
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                cmd_text = m.group(1).strip()
                break

        if cmd_text:
            if "```bash" not in cmd_text and "```" in cmd_text:
                cmd_text = "```bash\n" + cmd_text.replace("```", "") + "\n```"
            elif "```" not in cmd_text:
                cmd_text = "```bash\n" + cmd_text + "\n```"
            result["troubleshooting_commands"] = cmd_text

        # 如果没找到根因，用全文
        if not result["root_cause"]:
            result["root_cause"] = text[:800]

        # 如果没找到摘要，取根因的前100字
        if not result["summary"] and result["root_cause"]:
            first_line = result["root_cause"].split("\n")[0][:100]
            result["summary"] = first_line

        return result

    def _format_context(self, error_log: LogEntry, context_logs: List[LogEntry]) -> str:
        all_text = " ".join([error_log.message] + [l.message for l in context_logs])

        import re
        namespaces = set(re.findall(r'namespace[= ]"?(\w[\w-]*)"?', all_text, re.IGNORECASE))
        namespaces.update(re.findall(r'(\w[\w-]*)\/[a-z0-9-]+', all_text))
        pods = set(re.findall(r'pod[ "]+([a-z0-9-]+)', all_text, re.IGNORECASE))
        pods.update(re.findall(r'\/([a-z0-9-]+-[a-z0-9]+-[a-z0-9]+)', all_text))
        nodes = set(re.findall(r'node[ "]+([a-z0-9-]+)', all_text, re.IGNORECASE))
        nodes.update(re.findall(r'(worker-node-\d+)', all_text))

        lines = []
        lines.append("=== 错误日志 ===")
        lines.append(f"时间: {error_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"级别: {error_log.level.upper()}")
        lines.append(f"服务/组件: {error_log.service or 'unknown'}")
        lines.append(f"来源: {error_log.source or 'unknown'}")
        lines.append(f"错误信息: {error_log.message}")
        lines.append("")

        if namespaces or pods or nodes:
            lines.append("=== 从日志中提取的关键资源 ===")
            if namespaces:
                lines.append(f"涉及命名空间: {', '.join(sorted(namespaces)[:5])}")
            if pods:
                lines.append(f"涉及Pod: {', '.join(sorted(pods)[:5])}")
            if nodes:
                lines.append(f"涉及节点: {', '.join(sorted(nodes)[:5])}")
            lines.append("")

        lines.append(f"=== 上下文日志（前后{settings.CONTEXT_WINDOW_MINUTES}分钟，共{len(context_logs)}条） ===")
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
                "temperature": 0.2,
                "max_tokens": 3000,
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
                if resp.status_code >= 400:
                    print(f"[AIService] LLM API {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]

            print(f"[AIService] LLM response length: {len(content)}")

            result = self._extract_from_text(content)
            if result["summary"] and result["root_cause"] and result["suggestions"]:
                print(f"[AIService] Text extraction succeeded, summary: {result['summary'][:50]}")
                return result

            print(f"[AIService] Text extraction incomplete, trying JSON parse...")
            import re
            content_clean = re.sub(r"^```(?:json)?\s*", "", content.strip())
            content_clean = re.sub(r"\n?```\s*$", "", content_clean.strip())

            try:
                parsed = json.loads(content_clean.strip())
                if isinstance(parsed, dict) and "summary" in parsed:
                    print(f"[AIService] JSON parse success, keys: {list(parsed.keys())}")
                    return self._normalize_result(parsed)
            except json.JSONDecodeError:
                pass

            json_start = content_clean.find("{")
            if json_start >= 0:
                brace_count = 0
                json_end = -1
                in_string = False
                escape = False
                for i in range(json_start, len(content_clean)):
                    ch = content_clean[i]
                    if escape:
                        escape = False
                        continue
                    if ch == '\\':
                        escape = True
                        continue
                    if ch == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if ch == '{':
                            brace_count += 1
                        elif ch == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i
                                break

                if json_end > json_start:
                    json_str = content_clean[json_start:json_end + 1]
                    try:
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict) and "summary" in parsed:
                            print(f"[AIService] Brace-count JSON parse success")
                            return self._normalize_result(parsed)
                    except json.JSONDecodeError:
                        pass

            print(f"[AIService] All parsing failed, using raw content")
            return {
                "summary": content[:100].replace("\n", " "),
                "root_cause": content[:800],
                "impact_scope": "",
                "severity": "medium",
                "suggestions": ["查看日志详情进行排查", "联系运维人员处理"],
                "troubleshooting_commands": "",
            }
        except Exception as e:
            print(f"[AIService] LLM call error: {e}")
            return self._mock_analysis_text(context_text)

    async def _call_llm_incremental(self, previous_analysis, context_text: str) -> dict:
        if not self._current_config:
            prev_summary = previous_analysis.summary if previous_analysis else ""
            return {
                "summary": f"[增量更新] {prev_summary[:80]}",
                "root_cause": "新日志到达，正在持续观察中。（Mock模式，未接入真实LLM）",
                "impact_scope": previous_analysis.impact_scope if previous_analysis else "",
                "severity": previous_analysis.severity if previous_analysis else "medium",
                "suggestions": ["持续观察日志变化", "检查相关服务状态"],
                "troubleshooting_commands": previous_analysis.troubleshooting_commands if previous_analysis else "",
            }

        try:
            prev_summary = previous_analysis.summary or ""
            prev_root_cause = previous_analysis.root_cause or ""
            prev_severity = previous_analysis.severity or "medium"

            prev_sug = ""
            try:
                sugs = json.loads(previous_analysis.suggestions) if previous_analysis.suggestions else []
                if isinstance(sugs, list):
                    prev_sug = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sugs)])
                else:
                    prev_sug = str(sugs)
            except Exception:
                prev_sug = previous_analysis.suggestions or ""

            system_prompt = INCREMENTAL_PROMPT.format(
                previous_summary=prev_summary,
                previous_root_cause=prev_root_cause,
                previous_suggestions=prev_sug,
                previous_severity=prev_severity,
                context=context_text,
            )

            url = self._current_config["api_base"].rstrip("/") + "/chat/completions"
            payload = {
                "model": self._current_config["model_name"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "请进行增量分析并按格式输出。"},
                ],
                "temperature": 0.2,
                "max_tokens": 3000,
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
            print(f"[AIService] Incremental LLM response length: {len(content)}")

            result = self._extract_from_text(content)
            if result["summary"] and result["root_cause"]:
                return result

            try:
                parsed = json.loads(content.strip())
                if isinstance(parsed, dict) and "summary" in parsed:
                    return self._normalize_result(parsed)
            except Exception:
                pass

            return {
                "summary": f"[增量] {content[:80]}",
                "root_cause": content[:600],
                "impact_scope": "",
                "severity": prev_severity,
                "suggestions": ["继续观察", "检查新日志线索"],
                "troubleshooting_commands": "",
            }
        except Exception as e:
            print(f"[AIService] Incremental LLM call error: {e}")
            prev_summary = previous_analysis.summary or ""
            return {
                "summary": f"[增量更新] {prev_summary[:80]}",
                "root_cause": f"增量分析调用失败：{str(e)}",
                "impact_scope": previous_analysis.impact_scope if previous_analysis else "",
                "severity": previous_analysis.severity if previous_analysis else "medium",
                "suggestions": ["查看日志详情", "检查LLM服务状态"],
                "troubleshooting_commands": previous_analysis.troubleshooting_commands if previous_analysis else "",
            }

    def _mock_analysis(self, log_entry: LogEntry, context_logs: List[LogEntry]) -> dict:
        msg = log_entry.message.lower()

        if "connection refused" in msg or "timeout" in msg or "connect" in msg or "unable to connect" in msg:
            return {
                "summary": f"网络连接异常：{log_entry.message[:100]}",
                "root_cause": "检测到连接失败类错误。可能原因包括：1) 目标服务宕机或端口未监听；2) 网络策略/防火墙限制；3) DNS解析失败；4) 连接池耗尽导致新连接无法建立。",
                "impact_scope": "依赖该服务的所有业务请求失败，可能引发服务雪崩。",
                "suggestions": [
                    "检查目标服务状态和端口监听情况，确认服务是否正常运行",
                    "排查网络连通性：ping / telnet / nc 测试目标地址和端口",
                    "检查连接池配置，适当调大 max_connections 或优化连接复用",
                    "查看数据库/中间件的活跃连接数和慢查询情况",
                    "如果是瞬时故障，可尝试熔断/降级/重试机制",
                ],
                "troubleshooting_commands": "```bash\n# 检查目标服务端口\ntelnet <目标IP> <端口>\n\n# 检查网络连通性\nping <目标IP>\n\n# 查看网络连接数\nnetstat -an | grep <端口> | wc -l\n\n# 查看 DNS 解析\nnslookup <域名>\n```",
                "severity": "high",
            }
        elif "out of memory" in msg or "oom" in msg or "memory" in msg:
            return {
                "summary": f"内存不足错误：{log_entry.message[:100]}",
                "root_cause": "检测到内存溢出类错误。可能原因：1) 应用存在内存泄漏；2) 内存配置不足；3) 大对象/大结果集加载；4) 并发量突增。",
                "impact_scope": "进程可能被 OOM Killer 杀死，导致服务中断。",
                "suggestions": [
                    "立即重启服务恢复可用性，同时抓取 heap dump / pprof 用于事后分析",
                    "检查 JVM 堆内存 / Go runtime 内存配置，评估是否需要扩容",
                    "分析内存泄漏点：关注大对象创建、缓存未释放等问题",
                    "限流或降级，减少内存压力",
                    "增加内存监控告警，提前预警",
                ],
                "troubleshooting_commands": "```bash\n# 查看内存使用\nfree -h\n\n# 查看 OOM 日志\ndmesg -T | grep -i 'out of memory'\n\n# 查看进程内存\nps aux --sort=-%mem | head -10\n\n# 查看容器内存限制\nkubectl top pod <pod-name> -n <namespace>\n```",
                "severity": "critical",
            }
        elif "null" in msg or "nil" in msg or "pointer" in msg or "NoneType" in msg:
            return {
                "summary": f"空指针/空引用异常：{log_entry.message[:100]}",
                "root_cause": "检测到空指针类错误。通常是代码健壮性问题：1) 参数校验缺失；2) 返回值未判空；3) 配置缺失导致对象未初始化。",
                "impact_scope": "可能影响部分请求，具体影响范围取决于出错代码路径。",
                "suggestions": [
                    "定位出错代码行，检查空值来源",
                    "增加参数校验和防御性编程",
                    "补充单元测试覆盖边界条件",
                    "检查相关配置项是否完整",
                ],
                "troubleshooting_commands": "```bash\n# 查看完整错误堆栈\nkubectl logs <pod> --previous -n <namespace>\n\n# 搜索相关错误\nkubectl logs <pod> -n <namespace> | grep -A5 'null'\n\n# 检查配置\nkubectl get configmap -n <namespace>\n```",
                "severity": "medium",
            }
        else:
            error_count = sum(1 for l in context_logs if l.level == "error")
            warn_count = sum(1 for l in context_logs if l.level == "warn")
            return {
                "summary": f"日志错误：{log_entry.message[:100]}",
                "root_cause": f"在错误前后{settings.CONTEXT_WINDOW_MINUTES}分钟的上下文中，共发现 {error_count} 条 ERROR 和 {warn_count} 条 WARN 日志。结合上下文日志分析，问题可能涉及服务间依赖异常或资源瓶颈。",
                "impact_scope": f"共检测到 {error_count} 个错误，可能影响相关服务的正常功能。",
                "suggestions": [
                    "查看完整的错误堆栈信息，定位出错位置",
                    "检查相关依赖服务的健康状态",
                    "查看同一时间段的监控指标（CPU/内存/磁盘/网络）",
                    "对比正常时段日志，找出异常差异点",
                    "如问题持续，升级到资深工程师处理",
                ],
                "troubleshooting_commands": "```bash\n# 查看 Pod 状态\nkubectl get pods -n <namespace>\n\n# 查看 Pod 日志\nkubectl logs <pod> -n <namespace> --tail=100\n\n# 查看 Pod 事件\nkubectl describe pod <pod> -n <namespace>\n\n# 查看资源使用\nkubectl top pod -n <namespace>\n```",
                "severity": "medium",
            }

    def _mock_analysis_text(self, context_text: str) -> dict:
        return {
            "summary": "AI分析结果（Mock模式）",
            "root_cause": f"当前为Mock模式，未配置真实LLM模型。上下文长度：{len(context_text)}字符。请在系统配置中添加LLM模型以启用真实AI分析。",
            "impact_scope": "Mock模式下无法评估真实影响范围",
            "suggestions": [
                "在「模型配置」页面添加 LLM 模型配置",
                "支持所有 OpenAI 兼容的模型（DeepSeek、通义千问、Ollama本地模型等）",
                "添加后设为默认模型即可启用真实AI分析",
            ],
            "troubleshooting_commands": "```bash\n# 请先配置 LLM 模型\n# 支持所有 OpenAI 兼容接口\n```",
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

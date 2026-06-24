# LogInsight API 文档

AI 智能日志分析器 - 接口文档

## 基础信息

- **基础URL**: `http://localhost:8000`
- **API文档**: `http://localhost:8000/docs` (Swagger UI)
- **数据格式**: JSON

---

## 1. 日志管理 API

### 1.1 获取日志列表

```
GET /api/logs
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| level | string | 否 | 日志级别，多个用逗号分隔，如 `error,warn` |
| service | string | 否 | 服务名过滤 |
| source | string | 否 | 日志来源过滤 |
| keyword | string | 否 | 关键词模糊匹配 |
| regex | string | 否 | 正则表达式匹配 |
| start_time | datetime | 否 | 开始时间 (ISO格式) |
| end_time | datetime | 否 | 结束时间 (ISO格式) |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认50，最大500 |

**响应示例**:
```json
{
  "total": 1234,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": 1,
      "timestamp": "2024-06-19T10:23:23",
      "level": "error",
      "source": "webhook",
      "service": "db-service",
      "message": "Connection refused: unable to connect to PostgreSQL",
      "tags": ""
    }
  ]
}
```

### 1.2 获取单条日志

```
GET /api/logs/{log_id}
```

### 1.3 手动创建日志

```
POST /api/logs
```

**请求体**:
```json
{
  "level": "error",
  "message": "错误信息",
  "source": "webhook",
  "service": "api-gateway",
  "tags": ""
}
```

### 1.4 获取日志上下文

```
GET /api/logs/{log_id}/context?minutes=5
```

获取指定日志前后 N 分钟的上下文日志。

---

## 2. Webhook API

### 2.1 入站 Webhook（接收日志）

```
POST /api/webhook/inbound
```

支持三种格式：

**单条日志**:
```json
{
  "level": "error",
  "message": "错误信息",
  "service": "my-service",
  "source": "prometheus"
}
```

**批量日志**:
```json
{
  "logs": [
    {"level": "info", "message": "...", "service": "svc1"},
    {"level": "error", "message": "...", "service": "svc2"}
  ]
}
```

**告警格式** (Prometheus/Grafana 兼容):
```json
{
  "alerts": [
    {
      "status": "firing",
      "labels": {"alertname": "HighCPU", "service": "api"},
      "annotations": {"summary": "CPU使用率过高"}
    }
  ]
}
```

**响应**:
```json
{ "status": "received" }
```

### 2.2 出站 Webhook 配置管理

```
GET    /api/webhook/configs          # 列出所有配置
POST   /api/webhook/configs          # 创建配置
DELETE /api/webhook/configs/{id}     # 删除配置
POST   /api/webhook/test/{id}        # 测试Webhook
```

**创建配置请求体**:
```json
{
  "name": "飞书告警群",
  "url": "https://hooks.feishu.cn/...",
  "webhook_type": "outbound",
  "enabled": true,
  "secret": ""
}
```

---

## 3. AI 分析 API

### 3.1 触发日志分析

```
POST /api/analysis/log/{log_id}
```

触发对指定日志的 AI 根因分析（优先级高，立即执行）。

**响应**:
```json
{
  "log_id": 123,
  "analysis": {
    "id": 1,
    "log_id": 123,
    "status": "processing",
    "summary": "",
    "root_cause": "",
    "suggestions": "[]",
    "severity": "medium",
    "model_used": "gpt-3.5-turbo"
  }
}
```

### 3.2 获取分析结果

```
GET /api/analysis/log/{log_id}
```

### 3.3 分析结果列表

```
GET /api/analysis?page=1&page_size=20
```

---

## 4. 文件上传分析 API

### 4.1 上传文件并分析

```
POST /api/upload/analyze
Content-Type: multipart/form-data
```

**参数**:
- `file`: 日志文件 (.log/.txt/.json)
- `source`: 来源标识 (可选)

**响应**:
```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "total_lines": 0,
  "error_count": 0,
  "analyses": []
}
```

### 4.2 查询上传任务状态

```
GET /api/upload/task/{task_id}
```

### 4.3 所有上传任务列表

```
GET /api/upload/tasks
```

---

## 5. 实时日志流 API

### 5.1 SSE 实时日志流

```
GET /api/stream/logs
```

使用 Server-Sent Events (SSE) 推送实时日志。

**响应格式**:
```
data: {"id":1,"timestamp":"2024-06-19T10:23:23","level":"error","source":"webhook","service":"db","message":"..."}

data: {...}
```

---

## 6. 配置管理 API

### 6.1 LLM 模型配置

```
GET    /api/config/llm              # 列出所有模型配置
POST   /api/config/llm              # 添加模型配置
PUT    /api/config/llm/{id}         # 更新模型配置
DELETE /api/config/llm/{id}         # 删除模型配置
POST   /api/config/llm/{id}/set-default  # 设为默认模型
```

**创建配置请求体**:
```json
{
  "name": "DeepSeek",
  "provider": "openai_compatible",
  "api_base": "https://api.deepseek.com/v1",
  "api_key": "sk-xxxx",
  "model_name": "deepseek-chat",
  "is_default": true
}
```

### 6.2 系统配置信息

```
GET /api/config/system
```

返回日志保留策略、AI分析配置、LLM状态等系统信息。

---

## 7. 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

**HTTP 状态码**:
- `200` - 成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误

---

## 8. 快速开始示例

### 8.1 发送测试日志

```bash
curl -X POST http://localhost:8000/api/webhook/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {"level": "error", "message": "Connection refused to PostgreSQL", "service": "db-service"},
      {"level": "warn", "message": "Connection pool at 85%", "service": "db-pool"},
      {"level": "info", "message": "Request received", "service": "api-gateway"}
    ]
  }'
```

### 8.2 上传日志文件

```bash
curl -X POST http://localhost:8000/api/upload/analyze \
  -F "file=@/path/to/app.log"
```

### 8.3 触发AI分析

```bash
curl -X POST http://localhost:8000/api/analysis/log/1
```

---

## 9. 支持的模型服务商

所有兼容 OpenAI API 格式的服务商都支持：

| 服务商 | API Base | 模型示例 |
|--------|----------|----------|
| OpenAI | https://api.openai.com/v1 | gpt-3.5-turbo, gpt-4 |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |
| Ollama (本地) | http://localhost:11434/v1 | qwen2.5:7b, llama3.1 |
| 智谱AI | https://open.bigmodel.cn/api/paas/v4 | glm-4 |

---

## 10. 项目结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库连接
│   ├── models/            # SQLAlchemy 模型
│   ├── schemas/           # Pydantic 数据模型
│   ├── api/               # API 路由层
│   │   ├── logs.py        # 日志管理接口
│   │   ├── webhook.py     # Webhook 接口
│   │   ├── analysis.py    # AI分析接口
│   │   ├── upload.py      # 文件上传接口
│   │   ├── config.py      # 配置管理接口
│   │   └── stream.py      # 实时流接口
│   └── services/          # 业务逻辑层
│       ├── log_service.py    # 日志存储与查询
│       ├── filter_service.py # 过滤与正则匹配
│       ├── ai_service.py     # AI分析引擎
│       ├── webhook_service.py# Webhook推送
│       └── upload_service.py # 文件上传分析
├── requirements.txt
├── .env.example
└── ...

frontend/
└── index.html           # 前端单页应用
```

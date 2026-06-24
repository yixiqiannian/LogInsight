<div align="center">

# LogInsight

### 🤖 AI 智能日志分析器

**多源日志接入 · AI驱动根因分析 · 双向Webhook告警**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## ✨ 产品特性

### 多源日志接入
- 🌐 **Webhook 入站**：支持单条日志、批量日志、Prometheus/Grafana 告警格式
- 📁 **文件上传**：支持 .log / .txt / .json 格式，自动解析并分析
- ⚡ **实时流**：SSE 推送实时日志，自动重连

### 智能过滤与检索
- 🔍 **级别过滤**：ERROR / WARN / INFO / DEBUG 一键切换
- 🎯 **正则匹配**：支持正则表达式精准定位目标事件
- 🔤 **关键词搜索**：模糊匹配，快速定位
- 📊 **分页浏览**：支持海量日志分页查询

### AI 根因分析
- 🧠 **上下文关联**：自动获取 ERROR 前后 N 分钟上下文日志
- 🔬 **智能推理**：站在 SRE 专家角度分析根因链路
- 💡 **处理建议**：给出 3-5 条可执行的处理步骤，按优先级排序
- 🏷️ **严重分级**：critical / high / medium / low 四级判定
- 🔌 **多模型支持**：兼容所有 OpenAI 格式接口（DeepSeek、通义千问、Ollama 本地模型等）

### 双向 Webhook 告警
- 📥 **入站接收**：接收 Prometheus、Grafana、Alertmanager 等告警
- 📤 **出站推送**：分析结果推送到飞书、钉钉、Slack、企业微信
- 🤖 **自动触发**：检测到 ERROR 自动触发 AI 分析并推送

### 高性能架构
- ⚡ **批量写入**：内存队列 + 批量落库，应对高并发日志量
- 📦 **分级存储**：ERROR/WARN 长期保留，INFO/DEBUG 可配置过期
- 🔄 **异步分析**：AI 分析后台 Worker 异步处理，不阻塞日志接入

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Git

### 一键启动（Windows）

```bash
# 克隆项目
git clone https://github.com/yixiqiannian/LogInsight.git
cd LogInsight

# 双击启动
start.bat
```

### 手动启动

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制配置文件
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/Mac

# 5. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 访问地址

| 页面 | 地址 |
|------|------|
| 前端主页 | http://localhost:8000/ |
| API 文档 | http://localhost:8000/docs |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

## 📖 使用指南

### 1. 快速体验（Mock模式）
无需配置 LLM，直接启动即可体验。内置规则引擎可分析常见错误类型。

### 2. 配置真实 AI 模型

在前端「模型配置」页面添加模型，支持：

| 服务商 | API Base | 模型示例 |
|--------|----------|----------|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-3.5-turbo`, `gpt-4o` |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat` |
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| **智谱 AI** | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| **Ollama 本地** | `http://localhost:11434/v1` | `qwen2.5:7b`, `llama3.1` |

也可以编辑 `backend/.env` 文件配置默认模型：

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL_NAME=deepseek-chat
```

### 3. 接入日志

#### 方式一：Webhook 推送

```bash
curl -X POST http://localhost:8000/api/webhook/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {"level": "error", "message": "Connection refused to PostgreSQL", "service": "db-service"}
    ]
  }'
```

#### 方式二：上传日志文件

在前端「文件上传」页面选择日志文件，支持 .log / .txt / .json 格式。

#### 方式三：实时流

前端实时日志流页面，通过 SSE 自动接收新日志。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (SPA)                            │
│  日志分析 | 文件上传 | Webhook配置 | 模型配置                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────────┐
│                      FastAPI 后端                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  API 路由层  │  │  业务服务层  │  │    数据持久层        │ │
│  │  logs       │  │  log_service│  │    SQLite           │ │
│  │  webhook    │  │  ai_service │  │                     │ │
│  │  analysis   │  │  filter_svc │  │  log_entries        │ │
│  │  upload     │  │  upload_svc │  │  analysis_results   │ │
│  │  config     │  │  webhook_svc│  │  webhook_configs    │ │
│  │  stream     │  │             │  │  llm_configs        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    异步任务队列                          │  │
│  │  批量写入队列  |  AI分析队列  |  推送队列               │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 项目结构

```
LogInsight/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── api/               # API 路由层
│   │   │   ├── logs.py        # 日志管理
│   │   │   ├── webhook.py     # Webhook 接入
│   │   │   ├── analysis.py    # AI 分析
│   │   │   ├── upload.py      # 文件上传
│   │   │   ├── config.py      # 系统配置
│   │   │   └── stream.py      # 实时流
│   │   └── services/          # 业务逻辑层
│   │       ├── log_service.py     # 日志存储与查询
│   │       ├── filter_service.py  # 过滤与正则匹配
│   │       ├── ai_service.py      # AI 分析引擎
│   │       ├── webhook_service.py # Webhook 推送
│   │       └── upload_service.py  # 文件上传分析
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # 前端
│   └── index.html            # 单页应用
├── API.md                      # 完整 API 文档
├── start.bat                   # Windows 启动脚本
├── start.sh                    # Linux/Mac 启动脚本
└── README.md
```

---

## 📡 API 概览

完整 API 文档请访问：[API.md](API.md) 或 http://localhost:8000/docs

### 日志管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/logs` | 查询日志列表（支持过滤、分页） |
| GET | `/api/logs/{id}` | 获取单条日志详情 |
| POST | `/api/logs` | 手动创建日志 |
| GET | `/api/logs/{id}/context` | 获取日志上下文 |

### Webhook
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/webhook/inbound` | 入站接收日志/告警 |
| GET | `/api/webhook/configs` | 列出出站配置 |
| POST | `/api/webhook/configs` | 创建出站配置 |
| DELETE | `/api/webhook/configs/{id}` | 删除配置 |

### AI 分析
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analysis/log/{log_id}` | 触发日志分析 |
| GET | `/api/analysis/log/{log_id}` | 获取分析结果 |
| GET | `/api/analysis` | 分析结果列表 |

### 文件上传
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload/analyze` | 上传并分析日志文件 |
| GET | `/api/upload/task/{id}` | 查询上传任务状态 |

### 实时流
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stream/logs` | SSE 实时日志流 |

### 配置管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/llm` | 列出 LLM 模型配置 |
| POST | `/api/config/llm` | 添加模型配置 |
| POST | `/api/config/llm/{id}/set-default` | 设为默认模型 |
| GET | `/api/config/system` | 获取系统配置信息 |

---

## ⚙️ 配置说明

### 环境变量（backend/.env）

```env
# 服务配置
HOST=0.0.0.0
PORT=8000

# 数据库
DATABASE_URL=sqlite:///./loginsight.db

# LLM 模型
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=gpt-3.5-turbo

# 日志保留策略（天）
LOG_RETENTION_DAYS_INFO=7
LOG_RETENTION_DAYS_WARN=30
LOG_RETENTION_DAYS_ERROR=90
DEBUG_LOG_PERSIST=false

# AI 分析
CONTEXT_WINDOW_MINUTES=5
AUTO_ANALYZE_ERROR=true

# 飞书 Webhook
FEISHU_WEBHOOK_URL=
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境

```bash
# 克隆仓库
git clone https://github.com/yixiqiannian/LogInsight.git
cd LogInsight

# 安装开发依赖
cd backend
pip install -r requirements.txt

# 启动开发服务器（热重载）
uvicorn app.main:app --reload
```

### 提交代码

```bash
git add .
git commit -m "feat: 添加某某功能"
git push origin main
```

---

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果这个项目对你有帮助，别忘了给个 ⭐ Star 哦！**

Made with ❤️ by LogInsight Team

</div>

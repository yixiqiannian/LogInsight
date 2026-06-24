@echo off
chcp 65001 >nul
echo ============================================
echo   LogInsight - AI智能日志分析器
echo ============================================
echo.

cd /d "%~dp0backend"

if not exist ".env" (
    echo [提示] 未检测到 .env 文件，正在从 .env.example 创建...
    copy ".env.example" ".env"
    echo [完成] 请编辑 backend\.env 配置 LLM API 等信息
    echo.
)

if not exist "venv" (
    echo [提示] 未检测到虚拟环境，正在创建...
    python -m venv venv
    echo [完成] 虚拟环境创建成功
    echo.
    echo [提示] 正在安装依赖...
    call venv\Scripts\pip install -r requirements.txt
    echo [完成] 依赖安装完成
    echo.
)

echo [启动] 正在启动 LogInsight 服务...
echo.
call venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause

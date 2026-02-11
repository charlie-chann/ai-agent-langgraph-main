@echo off
echo ========================================
echo   Self-Evolving RAG System
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未找到，请先安装 Python
    pause
    exit /b 1
)

echo [2/3] 检查依赖...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo 📦 首次运行，正在安装依赖...
    pip install -r requirements.txt
)

echo [3/3] 检查 Ollama...
echo 请确保 Ollama 已启动: ollama serve
echo 模型检查: ollama list
echo.

echo 🚀 启动 Streamlit 界面...
streamlit run app.py --server.port 8501 --server.headless true

pause

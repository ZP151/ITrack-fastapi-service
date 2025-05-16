
. .\venv\Scripts\Activate.ps1

# 切换到项目目录
Set-Location C:\Users\Dell\source\repos\ITrack\chatbot_server

# 启动 FastAPI 服务，端口8000
uvicorn chatbot_server:app --reload --port 8000
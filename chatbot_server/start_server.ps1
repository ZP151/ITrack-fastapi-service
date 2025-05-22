. .\venv\Scripts\Activate.ps1

# 安装必要的依赖包
# pip install fastapi uvicorn pydantic sentence-transformers scikit-learn faiss-cpu

# 切换到项目目录
Set-Location C:\Users\Dell\source\repos\ITrack\chatbot_server

# 启动 FastAPI 服务，只使用单进程模式
uvicorn chatbot_server:app --host 127.0.0.1 --port 8000
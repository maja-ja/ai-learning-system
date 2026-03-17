import subprocess
import sys
import time
import os

def main():
    print("🚀 正在啟動 AI 教育工作站系統...")
    
    # 自動抓取專案的根目錄路徑
    root_dir = os.path.abspath(os.path.dirname(__file__))
    
    # 1. 啟動 FastAPI (指定去 backend 資料夾找 api.py)
    print("🧠 啟動 FastAPI 後端大腦...")
    fastapi_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api:app", "--port", "8000"],
        cwd=root_dir
    )
    
    time.sleep(2) # 等待後端啟動 2 秒
    
    # 2. 啟動 Streamlit (指定去 streamlit_app 資料夾找 app.py)
    print("🖥️ 啟動 Streamlit 講義與知識庫系統...")
    streamlit_process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_app/app.py", "--server.port", "8501", "--server.address", "127.0.0.1"],
        cwd=root_dir
    )
    
    try:
        # 保持執行直到按下 Ctrl+C
        fastapi_process.wait()
        streamlit_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 正在關閉系統...")
        fastapi_process.terminate()
        streamlit_process.terminate()
        print("✅ 系統已安全關閉。")

if __name__ == "__main__":
    main()
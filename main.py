import asyncio
import json
from pathlib import Path
from typing import List
from contextlib import asynccontextmanager
import redis.asyncio as aioredis

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from tasks import run_ai_processing_task
from websocket_manager import manager

# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(redis_listener())
    yield
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# --- App Initialization ---
app = FastAPI(title="AI Model Server", lifespan=lifespan)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static File Serving ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
app.mount("/results", StaticFiles(directory=RESULTS_DIR), name="results")

# --- [新增] Redis Pub/Sub 監聽器 ---
# 這個背景任務會在 FastAPI 啟動時自動運行
# 它會監聽 Redis 的 'progress_updates' 頻道
async def redis_listener():
    redis_client = None
    pubsub = None
    
    try:
        # 注意：這裡使用非同步的 redis client
        redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("progress_updates")
        print("Redis Pub/Sub 監聽器已啟動，正在監聽 'progress_updates' 頻道...")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    print(f"從 Redis 收到訊息: {message['data']}")
                    data = json.loads(message['data'])
                    client_id = data.get("client_id")
                    payload = data.get("payload")
                    if client_id and payload:
                        # 收到訊息後，透過 WebSocketManager 將其轉發給指定的前端客戶端
                        await manager.send_personal_message(payload, client_id)
                except json.JSONDecodeError as e:
                    print(f"JSON 解析錯誤: {e}")
                except Exception as e:
                    print(f"處理訊息時發生錯誤: {e}")
    except asyncio.CancelledError:
        print("Redis 監聽器被取消")
        raise
    except Exception as e:
        print(f"Redis 監聽器發生錯誤: {e}")
    finally:
        if pubsub:
            await pubsub.close()
        if redis_client:
            await redis_client.close()
        print("Redis 監聽器已清理並關閉")

# --- API Endpoints ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)

@app.post("/submit-task")
async def submit_task(files: List[UploadFile] = File(None), 
                      text: str = Form(...),
                      client_id: str = Form(...)
                      ):
    saved_file_paths = []
    if files:
        for file in files:
            file_path = UPLOAD_DIR / f"{Path(file.filename).stem}_{Path(file.filename).suffix}"
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            saved_file_paths.append(str(file_path))

    task = run_ai_processing_task.delay(
        client_id=client_id, 
        file_paths=saved_file_paths, 
        rule_text=text
    )
    return {"task_id": task.id}

@app.get("/download/{file_name}")
async def download_file(file_name: str):
    file_path = RESULTS_DIR / file_name
    if file_path.exists():
        return FileResponse(path=file_path, filename=file_name, media_type='application/octet-stream')
    return {"error": "File not found"}

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_html_path = BASE_DIR / "index.html"
    if index_html_path.exists():
        return index_html_path.read_text()
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)

@app.get("/health")
def health_check():
    return {"status": "ok"}


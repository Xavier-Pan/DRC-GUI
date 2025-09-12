from typing import Dict
from fastapi import WebSocket
import asyncio

class WebSocketManager:
    """
    管理所有 WebSocket 連線的類別
    """
    def __init__(self):
        # 使用 client_id 作為 key 來儲存連線
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """接受新的連線"""
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        """中斷連線"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        """向指定的 client_id 發送 JSON 訊息"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

# 建立一個全域共享的 manager 實例
# 這樣 FastAPI 和 Celery 都能匯入並使用同一個實例
manager = WebSocketManager()

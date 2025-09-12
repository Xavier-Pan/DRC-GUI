import time
import os
import json
from pathlib import Path
import redis

from celery_app import celery_app

# --- [新增] Redis Publisher ---
# 建立一個標準的 (同步) Redis 客戶端，專門用來發布訊息
redis_client = redis.from_url("redis://localhost:6379")

def update_progress_via_redis(client_id: str, payload: dict):
    """
    [修改] 輔助函式，現在透過 Redis Pub/Sub 發送進度更新
    """
    message = {
        "client_id": client_id,
        "payload": payload
    }
    # 將訊息發布到 'progress_updates' 頻道
    redis_client.publish("progress_updates", json.dumps(message))

def mock_ai_model(file_paths: list, rule_text: str):
    """模擬 AI 模型處理過程"""
    print(f"AI 模型開始處理... 檔案: {file_paths}, 規則: {rule_text}")
    time.sleep(5) 
    print("AI 模型處理完成。")
    return "AI_model_output.txt"

def mock_ftp_to_server_b(model_output_path: str):
    """模擬將結果 FTP 到 Server B"""
    print(f"正在將 {model_output_path} FTP 到 Server B...")
    time.sleep(2)
    print("FTP 傳輸完成。")

def mock_wait_for_server_b_response(client_id: str):
    """模擬等待 Server B 回傳結果"""
    print("等待 Server B 回傳結果...")
    time.sleep(3)
    
    image_file_name = f"{client_id}_result.png"
    gds_file_name = f"{client_id}_result.gds"
    
    # 確保 results 目錄存在
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    image_path = results_dir / image_file_name
    gds_path = results_dir / gds_file_name
    
    image_path.write_text("This is a placeholder for the result image.")
    gds_path.write_text("This is GDS file content.")
        
    print(f"已從 Server B 收到檔案: {image_file_name}, {gds_file_name}")
    return image_file_name, gds_file_name

@celery_app.task
def run_ai_processing_task(client_id: str, file_paths: list, rule_text: str):
    """Celery 主任務，串聯整個處理流程"""
    try:
        # [修改] 所有進度更新都改為透過 Redis 發布
        update_progress_via_redis(client_id, {"status": "processing", "message": "任務已開始，正在啟動 AI 模型..."})
        
        model_output_path = mock_ai_model(file_paths, rule_text)
        update_progress_via_redis(client_id, {"status": "processing", "message": "AI 模型處理完成，準備傳送到 Server B..."})
        
        mock_ftp_to_server_b(model_output_path)
        update_progress_via_redis(client_id, {"status": "processing", "message": "檔案已傳送到 Server B，正在等待回傳結果..."})
        
        image_name, gds_name = mock_wait_for_server_b_response(client_id)
        
        # 清理上傳的暫存檔案
        for path in file_paths:
            Path(path).unlink(missing_ok=True)

        final_payload = {
            "status": "completed",
            "message": "處理完成！",
            "image_url": f"/results/{image_name}",
            "gds_url": f"/download/{gds_name}"
        }
        update_progress_via_redis(client_id, final_payload)

    except Exception as e:
        print(f"任務失敗: {e}")
        update_progress_via_redis(client_id, {"status": "error", "message": f"錯誤：{e}"})

    return "任務流程結束"
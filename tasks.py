import time
import os
import json
from pathlib import Path
import redis
import ftplib
from typing import Tuple
from dotenv import load_dotenv

from celery_app import celery_app

# Load environment variables
load_dotenv()

# --- [新增] Redis Publisher ---
# 建立一個標準的 (同步) Redis 客戶端，專門用來發布訊息
redis_client = redis.from_url("redis://localhost:6379")

# --- FTP Configuration for Server B ---
FTP_SERVER_B = {
    'host': os.getenv('FTP_SERVER_B_HOST', 'your-server-b-hostname'),
    'port': int(os.getenv('FTP_SERVER_B_PORT', '21')),
    'username': os.getenv('FTP_SERVER_B_USER', 'your-username'),
    'password': os.getenv('FTP_SERVER_B_PASS', 'your-password'),
    'upload_dir': os.getenv('FTP_SERVER_B_UPLOAD_DIR', '/upload'),
    'download_dir': os.getenv('FTP_SERVER_B_DOWNLOAD_DIR', '/results')
}

class CustomFTP_TLS(ftplib.FTP_TLS):
    """Custom FTP_TLS class to handle TLS session reuse issues"""
    
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn,
                                          server_hostname=self.host,
                                          session=self.sock.session)  # Reuse TLS session
        return conn, size

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
    
    # 創建實際的輸出檔案
    output_path = "AI_model_output.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"AI 處理結果\n")
        f.write(f"輸入檔案: {file_paths}\n")
        f.write(f"規則: {rule_text}\n")
        f.write(f"處理時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("AI 模型處理完成。")
    return output_path

def ftp_to_server_b(model_output_path: str):
    """將結果 FTP 到 Server B"""
    try:
        print(f"正在將 {model_output_path} FTP 到 Server B...")
        
        ftp = CustomFTP_TLS()
        ftp.connect(FTP_SERVER_B['host'], FTP_SERVER_B['port'])
        ftp.auth() # 進行安全握手
        ftp.login(FTP_SERVER_B['username'], FTP_SERVER_B['password'])
        ftp.prot_p()  # 將資料傳輸通道也加密
        ftp.set_pasv(True)  # 使用被動模式
        
        # 切換到上傳目錄
        ftp.cwd(FTP_SERVER_B['upload_dir'])
        
        # 上傳檔案
        with open(model_output_path, 'rb') as file:
            filename = Path(model_output_path).name
            ftp.storbinary(f'STOR {filename}', file)
        
        ftp.quit()
        print("FTP 傳輸完成。")
        
    except Exception as e:
        print(f"FTP 上傳失敗: {e}")
        raise

def wait_for_server_b_response(client_id: str) -> Tuple[str, str]:
    """等待並下載 Server B 回傳結果"""
    print("等待 Server B 回傳結果...")
    
    image_file_name = f"{client_id}_result.png"
    gds_file_name = f"{client_id}_result.gds"
    
    # 確保 results 目錄存在
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    image_path = results_dir / image_file_name
    gds_path = results_dir / gds_file_name
    
    max_retries = 30  # 最多等待30次 (每次10秒)
    retry_interval = 10  # 每10秒檢查一次
    
    try:
        for attempt in range(max_retries):
            print(f"檢查 Server B 結果... (嘗試 {attempt + 1}/{max_retries})")
            
            ftp = CustomFTP_TLS()
            ftp.connect(FTP_SERVER_B['host'], FTP_SERVER_B['port'])
            ftp.auth() # 進行安全握手
            ftp.login(FTP_SERVER_B['username'], FTP_SERVER_B['password'])
            ftp.prot_p() #  將資料傳輸通道也加密
            ftp.set_pasv(True)  # 使用被動模式
            ftp.cwd(FTP_SERVER_B['download_dir'])
            
            # 列出可用檔案
            files = ftp.nlst()
            
            # 檢查所需的檔案是否存在
            if image_file_name in files and gds_file_name in files:
                print("找到結果檔案，開始下載...")
                
                # 下載 PNG 檔案
                with open(image_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {image_file_name}', f.write)
                
                # 下載 GDS 檔案
                with open(gds_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {gds_file_name}', f.write)
                
                ftp.quit()
                print(f"已從 Server B 下載檔案: {image_file_name}, {gds_file_name}")
                return image_file_name, gds_file_name
            
            # 如果檔案還沒準備好，等待後重試
            time.sleep(retry_interval)
        
        # 如果超過重試次數仍未找到檔案
        raise TimeoutError(f"等待 Server B 回傳結果超時 ({max_retries * retry_interval} 秒)")
        
    except Exception as e:
        print(f"從 Server B 下載檔案失敗: {e}")
        raise

@celery_app.task
def run_ai_processing_task(client_id: str, file_paths: list, rule_text: str):
    """Celery 主任務，串聯整個處理流程"""
    try:
        # [修改] 所有進度更新都改為透過 Redis 發布
        update_progress_via_redis(client_id, {"status": "processing", "message": "任務已開始，正在啟動 AI 模型..."})
        
        model_output_path = mock_ai_model(file_paths, rule_text)
        update_progress_via_redis(client_id, {"status": "processing", "message": "AI 模型處理完成，準備傳送到 Server B..."})
        
        ftp_to_server_b(model_output_path)
        update_progress_via_redis(client_id, {"status": "processing", "message": "檔案已傳送到 Server B，正在等待回傳結果..."})
        
        image_name, gds_name = wait_for_server_b_response(client_id)
        
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
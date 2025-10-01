import time
import os
import json
import zipfile
from pathlib import Path
import redis
import requests
from typing import Dict
from dotenv import load_dotenv

from celery_app import celery_app

# Load environment variables
load_dotenv()

# --- [新增] Redis Publisher ---
# 建立一個標準的 (同步) Redis 客戶端，專門用來發布訊息
redis_client = redis.from_url("redis://localhost:6379")

# --- API Configuration for Server B ---
API_SERVER_B = {
    'base_url': os.getenv('API_SERVER_B_URL', 'http://your-server-b-hostname:8001'),
    'upload_endpoint': os.getenv('API_SERVER_B_UPLOAD', '/api/v1/upload'),
    'status_endpoint': os.getenv('API_SERVER_B_STATUS', '/api/v1/status'),
    'download_endpoint': os.getenv('API_SERVER_B_DOWNLOAD', '/api/v1/download'),
    'api_key': os.getenv('API_SERVER_B_KEY', 'your-api-key'),
    'timeout': int(os.getenv('API_TIMEOUT', '30'))
}

def get_api_headers() -> Dict[str, str]:
    """Get API headers with authentication"""
    return {
        'Authorization': f'Bearer {API_SERVER_B["api_key"]}',
        'Content-Type': 'application/json'
    }

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

def upload_to_server_b(model_output_path: str, task_id: str) -> Dict:
    """將結果透過 API 上傳到 Server B"""
    try:
        print(f"正在將 {model_output_path} 透過 API 上傳到 Server B...")
        
        upload_url = f"{API_SERVER_B['base_url']}{API_SERVER_B['upload_endpoint']}"
        
        # 準備上傳的檔案和資料
        with open(model_output_path, 'rb') as file:
            files = {
                'file': (Path(model_output_path).name, file, 'application/octet-stream')
            }
            data = {
                'task_id': task_id,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            headers = {
                'Authorization': f'Bearer {API_SERVER_B["api_key"]}'
            }
            
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                headers=headers,
                timeout=API_SERVER_B['timeout']
            )
            
            response.raise_for_status()
            result = response.json()
            
        print(f"API 上傳完成。回應: {result}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"API 上傳失敗: {e}")
        raise
    except Exception as e:
        print(f"上傳過程發生錯誤: {e}")
        raise

def wait_for_server_b_response(task_id: str) -> Dict:
    """等待並下載 Server B 回傳批次結果"""
    print(f"等待 Server B 回傳批次結果... (Task ID: {task_id})")
    
    # 確保 results 目錄存在
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    max_retries = 30  # 最多等待30次 (每次10秒)
    retry_interval = 10  # 每10秒檢查一次
    
    try:
        for attempt in range(max_retries):
            print(f"檢查 Server B 結果... (嘗試 {attempt + 1}/{max_retries})")
            
            # 檢查任務狀態
            status_url = f"{API_SERVER_B['base_url']}{API_SERVER_B['status_endpoint']}/{task_id}"
            headers = get_api_headers()
            
            response = requests.get(status_url, headers=headers, timeout=API_SERVER_B['timeout'])
            response.raise_for_status()
            status_data = response.json()
            
            print(f"任務狀態: {status_data.get('status', 'unknown')}")
            
            # 如果任務完成，下載結果
            if status_data.get('status') == 'completed':
                print("任務完成，開始下載結果...")
                return download_results_from_server_b(task_id, status_data)
            
            # 如果任務失敗
            elif status_data.get('status') == 'failed':
                error_msg = status_data.get('error', '未知錯誤')
                raise Exception(f"Server B 處理失敗: {error_msg}")
            
            # 如果還在處理中，等待後重試
            time.sleep(retry_interval)
        
        # 如果超過重試次數仍未完成
        raise TimeoutError(f"等待 Server B 完成處理超時 ({max_retries * retry_interval} 秒)")
        
    except requests.exceptions.RequestException as e:
        print(f"API 請求失敗: {e}")
        raise
    except Exception as e:
        print(f"等待 Server B 回應失敗: {e}")
        raise

def download_results_from_server_b(task_id: str, status_data: Dict) -> Dict:
    """從 Server B 下載處理結果"""
    try:
        download_url = f"{API_SERVER_B['base_url']}{API_SERVER_B['download_endpoint']}/{task_id}"
        headers = get_api_headers()
        
        # 下載 ZIP 檔案
        response = requests.get(download_url, headers=headers, timeout=API_SERVER_B['timeout'], stream=True)
        response.raise_for_status()
        
        # 儲存下載的檔案
        results_dir = Path("results")
        zip_file_name = f"{task_id}_results.zip"
        zip_path = results_dir / zip_file_name
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"已從 Server B 下載結果檔案: {zip_file_name}")
        
        # 如果 status_data 包含 manifest 資訊，直接使用
        if 'manifest' in status_data:
            manifest_data = status_data['manifest']
            # 創建臨時 manifest 檔案
            manifest_path = results_dir / f"{task_id}_manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, ensure_ascii=False, indent=2)
            
            return extract_and_process_batch_results(task_id, zip_path, manifest_path)
        else:
            # 否則解壓縮後自動偵測檔案
            return extract_and_process_batch_results_auto(task_id, zip_path)
            
    except requests.exceptions.RequestException as e:
        print(f"下載結果失敗: {e}")
        raise
    except Exception as e:
        print(f"處理下載結果失敗: {e}")
        raise

def extract_and_process_batch_results_auto(task_id: str, zip_path: Path) -> Dict:
    """自動偵測並處理批次結果檔案"""
    try:
        # 建立任務專用目錄
        task_results_dir = Path("results") / task_id
        task_results_dir.mkdir(exist_ok=True)
        
        # 解壓縮 ZIP 檔案到任務目錄
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(task_results_dir)
        
        # 自動偵測檔案類型
        extracted_files = []
        png_files = []
        gds_files = []
        
        for file_path in task_results_dir.iterdir():
            if file_path.is_file():
                filename = file_path.name
                file_type = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
                
                extracted_files.append({
                    'filename': filename,
                    'type': file_type,
                    'description': f'{file_type.upper()} 檔案',
                    'url': f"/results/{task_id}/{filename}"
                })
                
                # 分類檔案
                if file_type == 'png':
                    png_files.append(filename)
                elif file_type == 'gds':
                    gds_files.append(filename)
        
        print(f"成功自動偵測並解壓縮 {len(extracted_files)} 個檔案到 {task_results_dir}")
        
        return {
            'batch_id': task_id,
            'total_count': len(extracted_files),
            'files': extracted_files,
            'png_files': png_files,
            'gds_files': gds_files,
            'zip_file': zip_path.name,
            'manifest': {'files': extracted_files}
        }
        
    except Exception as e:
        print(f"自動處理批次結果失敗: {e}")
        raise

def extract_and_process_batch_results(task_id: str, zip_path: Path, manifest_path: Path) -> Dict:
    """解壓縮並處理批次結果檔案"""
    try:
        # 讀取 manifest
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # 建立任務專用目錄
        task_results_dir = Path("results") / task_id
        task_results_dir.mkdir(exist_ok=True)
        
        # 解壓縮 ZIP 檔案到任務目錄
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(task_results_dir)
        
        # 準備回傳結果
        extracted_files = []
        png_files = []
        gds_files = []
        
        for file_info in manifest.get('files', []):
            file_path = task_results_dir / file_info['filename']
            if file_path.exists():
                extracted_files.append({
                    'filename': file_info['filename'],
                    'type': file_info['type'],
                    'description': file_info.get('description', ''),
                    'url': f"/results/{task_id}/{file_info['filename']}"
                })
                
                # 分類檔案
                if file_info['type'] == 'png':
                    png_files.append(file_info['filename'])
                elif file_info['type'] == 'gds':
                    gds_files.append(file_info['filename'])
        
        print(f"成功解壓縮 {len(extracted_files)} 個檔案到 {task_results_dir}")
        
        return {
            'batch_id': task_id,
            'total_count': len(extracted_files),
            'files': extracted_files,
            'png_files': png_files,
            'gds_files': gds_files,
            'zip_file': zip_path.name,
            'manifest': manifest
        }
        
    except Exception as e:
        print(f"處理批次結果失敗: {e}")
        raise

@celery_app.task(bind=True)
def run_ai_processing_task(self, client_id: str, file_paths: list, rule_text: str):
    """Celery 主任務，串聯整個處理流程"""
    try:
        # 獲取當前任務的 task_id
        task_id = self.request.id
        print(f"開始處理任務 - Client ID: {client_id}, Task ID: {task_id}")
        
        # [修改] 所有進度更新都改為透過 Redis 發布
        update_progress_via_redis(client_id, {"status": "processing", "message": "任務已開始，正在啟動 AI 模型..."})
        
        model_output_path = mock_ai_model(file_paths, rule_text)
        update_progress_via_redis(client_id, {"status": "processing", "message": "AI 模型處理完成，準備傳送到 Server B..."})
        
        upload_to_server_b(model_output_path, task_id)
        update_progress_via_redis(client_id, {"status": "processing", "message": "檔案已傳送到 Server B，正在等待回傳批次結果..."})
        
        batch_results = wait_for_server_b_response(task_id)  # 使用 task_id 而不是 client_id
        
        # 清理上傳的暫存檔案
        for path in file_paths:
            Path(path).unlink(missing_ok=True)

        final_payload = {
            "status": "completed",
            "message": f"批次處理完成！共產生 {batch_results['total_count']} 個檔案",
            "batch_results": batch_results,
            "zip_url": f"/results/{batch_results['zip_file']}",
            "files": batch_results['files']
        }
        update_progress_via_redis(client_id, final_payload)

    except Exception as e:
        print(f"任務失敗: {e}")
        update_progress_via_redis(client_id, {"status": "error", "message": f"錯誤：{e}"})

    return "任務流程結束"
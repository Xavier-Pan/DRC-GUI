"""
Server B API Setup Template
This file provides a complete template for setting up the API server on Server B
"""

import os
import json
import time
import zipfile
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Server B API for DRC Processing",
    description="API server for receiving AI processing requests and returning results",
    version="1.0.0"
)

# Security
security = HTTPBearer()

# Configuration
SERVER_B_CONFIG = {
    'port': int(os.getenv('SERVER_B_PORT', '8001')),
    'host': os.getenv('SERVER_B_HOST', '0.0.0.0'),
    'api_key': os.getenv('SERVER_B_API_KEY', 'server-b-api-key-change-me'),
    'upload_dir': Path(os.getenv('SERVER_B_UPLOAD_DIR', 'uploads')),
    'results_dir': Path(os.getenv('SERVER_B_RESULTS_DIR', 'results')),
    'processing_dir': Path(os.getenv('SERVER_B_PROCESSING_DIR', 'processing')),
    'callback_url': os.getenv('CALLBACK_URL', None)  # Optional callback to AI server
}

# Ensure directories exist
for dir_path in [SERVER_B_CONFIG['upload_dir'], SERVER_B_CONFIG['results_dir'], SERVER_B_CONFIG['processing_dir']]:
    dir_path.mkdir(exist_ok=True)

# Task status storage (in production, use a database)
task_status = {}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key authentication"""
    if credentials.credentials != SERVER_B_CONFIG['api_key']:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

def simulate_processing(task_id: str, input_file_path: Path):
    """
    Simulate the actual processing that Server B would do
    Replace this with your actual processing logic
    """
    print(f"開始處理任務 {task_id}...")
    
    # Update task status
    task_status[task_id] = {
        'status': 'processing',
        'message': 'Processing started',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Simulate processing time (replace with actual processing)
    time.sleep(5)
    
    # Create mock results
    results_dir = SERVER_B_CONFIG['results_dir'] / task_id
    results_dir.mkdir(exist_ok=True)
    
    # Generate mock output files
    output_files = []
    
    # Create a mock PNG file
    png_file = results_dir / f"{task_id}_output.png"
    with open(png_file, 'w') as f:
        f.write(f"Mock PNG content for task {task_id}")
    output_files.append({
        'filename': png_file.name,
        'type': 'png',
        'description': 'Generated layout image'
    })
    
    # Create a mock GDS file
    gds_file = results_dir / f"{task_id}_layout.gds"
    with open(gds_file, 'w') as f:
        f.write(f"Mock GDS content for task {task_id}")
    output_files.append({
        'filename': gds_file.name,
        'type': 'gds',
        'description': 'Generated layout file'
    })
    
    # Create manifest
    manifest = {
        'task_id': task_id,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'files': output_files,
        'total_count': len(output_files)
    }
    
    manifest_file = results_dir / f"{task_id}_manifest.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    # Create ZIP file with all results
    zip_file = SERVER_B_CONFIG['results_dir'] / f"{task_id}_results.zip"
    with zipfile.ZipFile(zip_file, 'w') as zf:
        for file_info in output_files:
            file_path = results_dir / file_info['filename']
            zf.write(file_path, file_info['filename'])
        zf.write(manifest_file, manifest_file.name)
    
    # Update task status to completed
    task_status[task_id] = {
        'status': 'completed',
        'message': 'Processing completed successfully',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'manifest': manifest,
        'zip_file': zip_file.name
    }
    
    print(f"任務 {task_id} 處理完成")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Server B API for DRC Processing", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "active_tasks": len([t for t in task_status.values() if t['status'] == 'processing'])
    }

@app.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    task_id: str = Form(...),
    timestamp: Optional[str] = Form(None),
    api_key: str = Depends(verify_api_key)
):
    """
    Receive file upload from AI server
    """
    try:
        print(f"收到上傳請求: {file.filename} (Task ID: {task_id})")
        
        # Save uploaded file
        upload_path = SERVER_B_CONFIG['upload_dir'] / f"{task_id}_{file.filename}"
        
        with open(upload_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'received',
            'message': 'File uploaded successfully, queued for processing',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'input_file': str(upload_path)
        }
        
        # Start processing in background (in production, use proper task queue)
        import threading
        processing_thread = threading.Thread(
            target=simulate_processing,
            args=(task_id, upload_path)
        )
        processing_thread.daemon = True
        processing_thread.start()
        
        return {
            "success": True,
            "message": "File uploaded and processing started",
            "task_id": task_id,
            "filename": file.filename,
            "size": len(content)
        }
        
    except Exception as e:
        print(f"上傳失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/v1/status/{task_id}")
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Check task processing status
    """
    try:
        if task_id not in task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        
        status_info = task_status[task_id].copy()
        
        # Remove internal fields
        status_info.pop('input_file', None)
        
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"檢查狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/api/v1/download/{task_id}")
async def download_results(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Download processing results
    """
    try:
        if task_id not in task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        
        status_info = task_status[task_id]
        
        if status_info['status'] != 'completed':
            raise HTTPException(status_code=400, detail="Task not completed yet")
        
        zip_file_path = SERVER_B_CONFIG['results_dir'] / status_info['zip_file']
        
        if not zip_file_path.exists():
            raise HTTPException(status_code=404, detail="Result file not found")
        
        return FileResponse(
            path=zip_file_path,
            filename=status_info['zip_file'],
            media_type='application/zip'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"下載失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/api/v1/tasks")
async def list_tasks(
    api_key: str = Depends(verify_api_key)
):
    """
    List all tasks and their status
    """
    try:
        return {
            "tasks": task_status,
            "total_count": len(task_status)
        }
        
    except Exception as e:
        print(f"列出任務失敗: {e}")
        raise HTTPException(status_code=500, detail=f"List tasks failed: {str(e)}")

@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Delete task and clean up files
    """
    try:
        if task_id not in task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Clean up files
        task_results_dir = SERVER_B_CONFIG['results_dir'] / task_id
        if task_results_dir.exists():
            import shutil
            shutil.rmtree(task_results_dir)
        
        # Remove ZIP file
        zip_file = SERVER_B_CONFIG['results_dir'] / f"{task_id}_results.zip"
        if zip_file.exists():
            zip_file.unlink()
        
        # Remove from status
        del task_status[task_id]
        
        return {"success": True, "message": f"Task {task_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"刪除任務失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Delete task failed: {str(e)}")

if __name__ == "__main__":
    print(f"啟動 Server B API 伺服器...")
    print(f"地址: http://{SERVER_B_CONFIG['host']}:{SERVER_B_CONFIG['port']}")
    print(f"API Key: {SERVER_B_CONFIG['api_key']}")
    print(f"上傳目錄: {SERVER_B_CONFIG['upload_dir']}")
    print(f"結果目錄: {SERVER_B_CONFIG['results_dir']}")
    
    uvicorn.run(
        "server_b_api_setup:app",
        host=SERVER_B_CONFIG['host'],
        port=SERVER_B_CONFIG['port'],
        reload=True
    )
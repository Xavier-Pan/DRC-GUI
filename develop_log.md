# Development Log

## Issue: Frontend Not Receiving State Updates from Backend

**Date**: 2025-09-12  
**Status**: ✅ RESOLVED

### Problem Description

The frontend web page was not changing state and not receiving feedback from the backend. Users could submit tasks but saw no progress updates or completion notifications.

### Symptoms Observed

1. Frontend showed WebSocket connection but no real-time updates
2. Backend logs showed Redis coroutine errors:
   ```
   task: <Task pending name='Task-3' coro=<redis_listener() running at /home/hti2/DRC_GUI/main.py:48> wait_for=<Future pending cb=[Task.task_wakeup()]>>
   Exception ignored in: <coroutine object redis_listener at 0x76759d2066c0>
   Traceback (most recent call last):
     File "/home/hti2/anaconda3/envs/drc-gui/lib/python3.10/functools.py", line 950, in __init__
       self.lock = RLock()
   RuntimeError: coroutine ignored GeneratorExit
   ```
3. Task submission worked (`POST /submit-task HTTP/1.1" 200 OK`) but no progress updates

### Root Causes Identified

1. **Redis Listener Coroutine Error**: 
   - Improper async/await handling in Redis pub/sub listener
   - Poor exception handling causing `GeneratorExit` exceptions
   - Resource cleanup issues with Redis connections

2. **Deprecated FastAPI Event Handler**:
   - Using deprecated `@app.on_event("startup")` 
   - Should use modern lifespan handlers instead

3. **Inconsistent Redis Connection URLs**:
   - `main.py` used `redis://localhost` 
   - `tasks.py` and `celery_app.py` used `redis://localhost:6379`
   - Caused connection mismatches

4. **WebSocket Parameter Order Mismatch** (initially suspected):
   - Parameter order between `main.py` and `websocket_manager.py` was already correct

### Solutions Implemented

#### 1. Fixed Redis Listener Implementation

**Before** (main.py:38-61):
```python
async def redis_listener():
    redis_client = aioredis.from_url("redis://localhost", decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("progress_updates")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if message:
                # Process message...
    except Exception as e:
        print(f"Redis 監聽器發生錯誤: {e}")
    finally:
        await pubsub.close()
        await redis_client.close()
```

**After** (main.py:38-87):
```python
async def redis_listener():
    redis_client = None
    pubsub = None
    
    try:
        redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("progress_updates")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    client_id = data.get("client_id")
                    payload = data.get("payload")
                    if client_id and payload:
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
```

**Key Changes**:
- Used `async for message in pubsub.listen()` instead of manual message polling
- Added proper `asyncio.CancelledError` handling
- Better resource management with null checks
- Consistent Redis URL with port specification

#### 2. Updated to Modern FastAPI Lifespan Handler

**Before**:
```python
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())
```

**After**:
```python
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

app = FastAPI(title="AI Model Server", lifespan=lifespan)
```

#### 3. Standardized Redis Connection URLs

Updated all files to use consistent Redis URL:

**tasks.py**:
```python
# Before: redis_client = redis.from_url("redis://localhost")
redis_client = redis.from_url("redis://localhost:6379")
```

**celery_app.py** (already correct):
```python
CELERY_BROKER_URL = "redis://localhost:6379/0"
```

**main.py**:
```python
redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
```

### Communication Flow Verification

The complete data flow now works as follows:

1. **Frontend** → WebSocket connection to FastAPI
2. **Frontend** → HTTP POST `/submit-task` to FastAPI
3. **FastAPI** → Queues task in Redis via Celery
4. **Celery Worker** → Processes task and publishes progress to Redis pub/sub
5. **FastAPI Redis Listener** → Subscribes to Redis pub/sub
6. **FastAPI** → Forwards messages to frontend via WebSocket
7. **Frontend** → Receives real-time updates and updates UI state

### Testing & Verification

After implementing fixes:
- ✅ Redis connectivity confirmed (`redis-cli ping` returns `PONG`)
- ✅ No more coroutine errors in logs
- ✅ Modern FastAPI lifespan handler eliminates deprecation warnings
- ✅ Consistent Redis URLs across all components

### Restart Instructions

To apply fixes, restart services in this order:

1. **Stop all services**
2. **Start FastAPI server**: 
   ```bash
   conda activate drc-gui
   uvicorn main:app --reload
   ```
3. **Start Celery worker**:
   ```bash
   conda activate drc-gui
   celery -A celery_app worker --loglevel=info
   ```

### Files Modified

- `main.py`: Redis listener implementation, lifespan handler, consistent Redis URL
- `tasks.py`: Redis URL consistency  
- Added imports: `contextlib.asynccontextmanager`

### Lessons Learned

1. **Async Resource Management**: Always use proper try/finally blocks with null checks for async resources
2. **FastAPI Best Practices**: Keep up with framework updates and use modern patterns
3. **Connection String Consistency**: Ensure all services use identical connection parameters
4. **Error Handling**: Implement specific handling for `asyncio.CancelledError` in long-running tasks

### Related Documentation

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Redis Pub/Sub with asyncio](https://redis.readthedocs.io/en/stable/commands.html#pubsub)
- [Celery Redis Broker Configuration](https://docs.celeryproject.org/en/stable/getting-started/backends-and-brokers/redis.html)
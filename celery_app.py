from celery import Celery

# 這裡使用 Redis 作為訊息中間人 (Broker) 和結果後端 (Backend)
# 在生產環境中，請確保 Redis 服務正在運行
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

celery_app = Celery(
    "tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks"] # 要包含的任務模組
)

celery_app.conf.update(
    task_track_started=True,
)

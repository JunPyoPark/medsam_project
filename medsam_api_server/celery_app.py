import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """Celery 앱 생성 및 설정"""
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    app = Celery(
        "medsam2_gpu_service",
        broker=broker_url,
        backend=result_backend,
        include=[
            "medsam_api_server.tasks.segmentation",
        ],
    )

    # GPU 작업에 최적화된 설정
    app.conf.update(
        # 직렬화 설정
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        
        # 시간대 설정
        timezone="UTC",
        enable_utc=True,
        
        # 작업 추적 설정
        task_track_started=True,
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # 결과 설정
        result_expires=3600 * 24,  # 24시간
        result_persistent=True,
        
        # 워커 설정 (GPU 작업에 최적화)
        worker_concurrency=1,  # GPU는 동시 처리 제한
        worker_prefetch_multiplier=1,  # 메모리 사용량 제한
        task_acks_late=True,  # 작업 완료 후 ACK
        worker_max_tasks_per_child=100,  # 메모리 누수 방지 (모델 로딩 오버헤드 감소를 위해 증가)
        
        # 작업 라우팅
        task_routes={
            "generate_initial_mask": {"queue": "gpu_tasks"},
            "propagate_3d_mask": {"queue": "gpu_tasks"},
            "cleanup_old_results": {"queue": "maintenance_tasks"},
        },
        
        # 큐 설정
        task_default_queue="gpu_tasks",
        task_create_missing_queues=True,
        
        # 재시도 설정
        task_default_retry_delay=60,  # 1분
        task_max_retries=3,
        
        # 타임아웃 설정
        task_soft_time_limit=1800,  # 30분 소프트 타임아웃
        task_time_limit=2400,  # 40분 하드 타임아웃
        
        # 로그 설정
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    )

    return app


# Celery 워커 이벤트 핸들러
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """워커 시작시 실행"""
    logger.info("🚀 MedSAM2 GPU Worker is ready!")
    
    # GPU 상태 확인
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
            logger.info(f"✅ GPU available: {gpu_count} devices, Primary: {gpu_name}")
        else:
            logger.warning("⚠️ No GPU available, running in CPU mode")
    except ImportError:
        logger.warning("⚠️ PyTorch not available")
    
    # 모델 매니저 초기화 (실제 로딩은 첫 작업시)
    try:
        from medsam_api_server.core.model_manager import get_model_manager
        model_manager = get_model_manager()
        logger.info("✅ Model manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize model manager: {e}")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """워커 종료시 실행"""
    logger.info("🛑 MedSAM2 GPU Worker shutting down...")
    
    # 모델 언로딩
    try:
        from medsam_api_server.core.model_manager import get_model_manager
        model_manager = get_model_manager()
        model_manager.unload_model()
        logger.info("✅ Model unloaded")
    except Exception as e:
        logger.error(f"❌ Error during model unloading: {e}")
    
    # GPU 메모리 정리
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("✅ GPU memory cleared")
    except ImportError:
        pass
    
    logger.info("👋 MedSAM2 GPU Worker stopped")


# Celery 앱 인스턴스 생성
celery_app = create_celery_app() 
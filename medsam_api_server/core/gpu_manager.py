"""
GPU 자원 관리 모듈

여러 사용자가 동시에 GPU를 사용할 때 자원을 효율적으로 관리합니다.
- GPU 메모리 모니터링
- 작업 큐 관리
- 동시 실행 제한
"""

import os
import time
import psutil
import logging
from typing import Dict, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock, RLock
from medsam_api_server.celery_app import celery_app

try:
    import GPUtil
    import pynvml
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    logging.warning("GPU monitoring libraries not available")

logger = logging.getLogger(__name__)


@dataclass
class GPUStatus:
    """GPU 상태 정보"""
    gpu_id: int
    memory_used: float  # MB
    memory_total: float  # MB
    memory_percent: float
    temperature: float  # Celsius
    utilization: float  # Percent
    is_available: bool


@dataclass
class JobInfo:
    """작업 정보"""
    job_id: str
    task_type: str  # 'initial_mask' or 'propagation'
    start_time: float
    estimated_duration: float  # seconds
    memory_requirement: float  # MB


class GPUResourceManager:
    """GPU 자원 관리자"""
    
    def __init__(self, gpu_memory_limit: float = 0.8, max_concurrent_jobs: int = 2):
        self.gpu_memory_limit = gpu_memory_limit  # 사용 가능한 GPU 메모리 비율
        self.max_concurrent_jobs = max_concurrent_jobs
        self._lock = RLock()
        self._active_jobs: Dict[str, JobInfo] = {}
        
        # 캐싱을 위한 변수
        self._gpu_status_cache: Dict[int, tuple[float, GPUStatus]] = {}  # {gpu_id: (timestamp, status)}
        self._queue_length_cache: tuple[float, int] = (0.0, 0)  # (timestamp, length)
        self._cache_ttl = 2.0  # 캐시 유효 시간 (초)
        
        # GPU 초기화
        if GPU_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                logger.info(f"Initialized GPU manager with {self.gpu_count} GPUs")
            except Exception as e:
                logger.error(f"Failed to initialize GPU manager: {e}")
                self.gpu_count = 0
        else:
            self.gpu_count = 0
            logger.warning("GPU not available, running in CPU mode")
    
    def get_gpu_status(self, gpu_id: int = 0) -> Optional[GPUStatus]:
        """GPU 상태 조회"""
        if not GPU_AVAILABLE or gpu_id >= self.gpu_count:
            # CPU 모드에서는 가상 GPU 상태 반환
            if self.gpu_count == 0:
                return GPUStatus(
                    gpu_id=0,
                    memory_used=0.0,
                    memory_total=1000.0,  # 가상 메모리
                    memory_percent=0.0,
                    temperature=0.0,
                    utilization=0.0,
                    is_available=len(self._active_jobs) < self.max_concurrent_jobs
                )
            return None
            
        # 캐시 확인
        current_time = time.time()
        if gpu_id in self._gpu_status_cache:
            timestamp, cached_status = self._gpu_status_cache[gpu_id]
            if current_time - timestamp < self._cache_ttl:
                return cached_status

        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            
            # 메모리 정보
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used = mem_info.used / 1024 / 1024  # MB
            memory_total = mem_info.total / 1024 / 1024  # MB
            memory_percent = (mem_info.used / mem_info.total) * 100
            
            # 온도 정보
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                temperature = 0.0
            
            # 사용률 정보
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                utilization = util.gpu
            except:
                utilization = 0.0
            
            # 사용 가능 여부 판단
            is_available = (
                memory_percent < (self.gpu_memory_limit * 100) and
                len(self._active_jobs) < self.max_concurrent_jobs and
                temperature < 85  # 온도 제한
            )
            
            status = GPUStatus(
                gpu_id=gpu_id,
                memory_used=memory_used,
                memory_total=memory_total,
                memory_percent=memory_percent,
                temperature=temperature,
                utilization=utilization,
                is_available=is_available
            )
            
            # 캐시 업데이트
            self._gpu_status_cache[gpu_id] = (current_time, status)
            return status
            
        except Exception as e:
            logger.warning(
                "Failed to get GPU status via NVML (%s). Falling back to simplified status.",
                e,
            )
            fallback_total = 8192.0  # MB, reasonable default for MIG slice
            return GPUStatus(
                gpu_id=gpu_id,
                memory_used=0.0,
                memory_total=fallback_total,
                memory_percent=0.0,
                temperature=0.0,
                utilization=0.0,
                is_available=len(self._active_jobs) < self.max_concurrent_jobs,
            )
    
    def can_accept_job(self, task_type: str, estimated_memory: float = 2000) -> bool:
        """새 작업을 수용할 수 있는지 확인"""
        # 1. GPU 상태 확인 (Lock 없이 수행 - NVML 호출이 느릴 수 있음)
        # CPU 모드에서는 항상 True
        if self.gpu_count > 0:
            gpu_status = self.get_gpu_status()
            if not gpu_status or not gpu_status.is_available:
                return False
            
            # 메모리 요구사항 확인
            available_memory = gpu_status.memory_total * self.gpu_memory_limit - gpu_status.memory_used
            if estimated_memory > available_memory:
                return False

        # 2. 동시 작업 수 확인 (Lock 필요 - _active_jobs 접근)
        with self._lock:
            # 동시 작업 수 제한
            if len(self._active_jobs) >= self.max_concurrent_jobs:
                return False
            
            # 3. 큐 대기열 확인 (Celery Inspection)
            # 실제 워커가 바쁜지 확인하기 위해 큐 깊이를 체크
            try:
                # 캐시 확인
                current_time = time.time()
                timestamp, cached_length = self._queue_length_cache
                
                if current_time - timestamp < self._cache_ttl:
                    queue_length = cached_length
                else:
                    # Redis 브로커에서 직접 큐 길이 확인 (더 빠름)
                    with celery_app.connection_or_acquire() as conn:
                        # 'gpu_tasks' 큐의 길이 확인
                        queue_length = conn.default_channel.client.llen("gpu_tasks")
                        # 캐시 업데이트
                        self._queue_length_cache = (current_time, queue_length)
                
                # 대기열이 너무 길면 거부 (워커 수의 2배 이상 대기 중이면 Busy로 판단)
                # 워커 8개 * 2 = 16개
                if queue_length > (self.max_concurrent_jobs * 4):
                    logger.warning(f"System busy: {queue_length} tasks in queue")
                    return False
            except Exception as e:
                logger.warning(f"Failed to check queue length: {e}")
                # 큐 확인 실패 시에는 일단 허용 (보수적 접근)
            
            return True
    
    @contextmanager
    def acquire_gpu(self, job_id: str, task_type: str, estimated_duration: float = 60):
        """GPU 자원 획득 (컨텍스트 매니저)"""
        if not self.can_accept_job(task_type):
            raise RuntimeError("Resources not available")
        
        job_info = JobInfo(
            job_id=job_id,
            task_type=task_type,
            start_time=time.time(),
            estimated_duration=estimated_duration,
            memory_requirement=2000  # 기본값
        )
        
        with self._lock:
            self._active_jobs[job_id] = job_info
            device_info = "GPU" if self.gpu_count > 0 else "CPU"
            logger.info(f"Acquired {device_info} for job {job_id} ({task_type})")
        
        try:
            yield job_info
        finally:
            with self._lock:
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
                    duration = time.time() - job_info.start_time
                    device_info = "GPU" if self.gpu_count > 0 else "CPU"
                    logger.info(f"Released {device_info} for job {job_id}, duration: {duration:.2f}s")
    
    def get_active_jobs(self) -> List[JobInfo]:
        """활성 작업 목록 조회"""
        with self._lock:
            return list(self._active_jobs.values())
    
    def get_queue_position(self, job_id: str) -> Optional[int]:
        """큐에서의 위치 반환 (0부터 시작, None이면 큐에 없음)"""
        try:
            # 캐시 확인
            current_time = time.time()
            timestamp, cached_length = self._queue_length_cache
            
            if current_time - timestamp < self._cache_ttl:
                return cached_length
                
            with celery_app.connection_or_acquire() as conn:
                # Redis 리스트에서 job_id가 포함된 태스크 찾기 (비효율적일 수 있으나 정확함)
                # 실제로는 Celery가 태스크 ID로 관리하므로 job_id로 직접 찾기는 어려움
                # 여기서는 단순히 큐 길이만 반환하거나, 예상 대기 시간을 반환하는 것이 현실적
                
                queue_length = conn.default_channel.client.llen("gpu_tasks")
                
                # 캐시 업데이트
                self._queue_length_cache = (current_time, queue_length)
                return queue_length
        except Exception as e:
            logger.error(f"Failed to get queue position: {e}")
            return None
    
    def cleanup_stale_jobs(self, max_age_hours: float = 24):
        """오래된 작업 정리"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self._lock:
            stale_jobs = [
                job_id for job_id, job_info in self._active_jobs.items()
                if (current_time - job_info.start_time) > max_age_seconds
            ]
            
            for job_id in stale_jobs:
                del self._active_jobs[job_id]
                logger.warning(f"Cleaned up stale job: {job_id}")
    
    def get_system_info(self) -> Dict:
        """시스템 정보 조회"""
        info = {
            "cpu_percent": psutil.cpu_percent(interval=None),  # Non-blocking call
            "memory": dict(psutil.virtual_memory()._asdict()),
            "active_jobs": len(self._active_jobs),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "gpu_available": GPU_AVAILABLE,
            "gpu_count": self.gpu_count
        }
        
        # GPU 또는 CPU 상태 정보
        gpu_status = self.get_gpu_status()
        if gpu_status:
            info["gpu"] = {
                "memory_used_mb": gpu_status.memory_used,
                "memory_total_mb": gpu_status.memory_total,
                "memory_percent": gpu_status.memory_percent,
                "temperature": gpu_status.temperature,
                "utilization": gpu_status.utilization,
                "is_available": gpu_status.is_available
            }
        
        return info


# 전역 GPU 관리자 인스턴스
_gpu_manager: Optional[GPUResourceManager] = None
_gpu_manager_lock = Lock()


def get_gpu_manager() -> GPUResourceManager:
    """GPU 관리자 싱글톤 인스턴스 반환 (스레드 안전)"""
    global _gpu_manager
    if _gpu_manager is None:
        with _gpu_manager_lock:
            # Double-check locking pattern
            if _gpu_manager is None:
                gpu_memory_limit = float(os.getenv("GPU_MEMORY_LIMIT", "0.8"))
                max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
                _gpu_manager = GPUResourceManager(gpu_memory_limit, max_concurrent_jobs)
    return _gpu_manager 
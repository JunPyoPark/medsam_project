"""
MedSAM2 분할 작업

Celery를 사용한 비동기 GPU 작업 처리
"""

import os
import time
import logging
import traceback
from typing import Dict, Any, Optional
from celery import current_task
from celery.exceptions import Retry

from medsam_api_server.celery_app import celery_app
from medsam_api_server.core.inference_engine import get_inference_engine
from medsam_api_server.core.gpu_manager import get_gpu_manager

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_initial_mask")
def generate_initial_mask_task(
    self,
    job_id: str,
    volume_path: str,
    slice_index: int,
    bounding_box: list,
    window_level: Optional[list] = None
) -> Dict[str, Any]:
    """
    2D 초기 마스크 생성 작업
    
    Args:
        job_id: 작업 ID
        volume_path: NIfTI 파일 경로
        slice_index: 대상 슬라이스 인덱스
        bounding_box: [x1, y1, x2, y2] 좌표
        window_level: [window, level] 윈도우 레벨
        
    Returns:
        Dict containing task result
    """
    logger.info(f"Starting initial mask generation task for job {job_id}")
    
    try:
        # 작업 상태 업데이트
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "initial_mask",
                "progress": 0,
                "current_operation": "Initializing..."
            }
        )
        
        # GPU 자원 확인
        gpu_manager = get_gpu_manager()
        if not gpu_manager.can_accept_job("initial_mask"):
            raise RuntimeError("Resources not available")
        
        # 진행률 업데이트
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "initial_mask",
                "progress": 20,
                "current_operation": "Loading model..."
            }
        )
        
        # 추론 엔진 실행
        inference_engine = get_inference_engine()
        
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "initial_mask",
                "progress": 50,
                "current_operation": "Running inference..."
            }
        )
        
        start_time = time.time()
        result = inference_engine.generate_initial_mask(
            job_id=job_id,
            volume_path=volume_path,
            slice_index=slice_index,
            bounding_box=bounding_box,
            window_level=window_level
        )
        processing_time = time.time() - start_time
        
        # 최종 결과
        final_result = {
            "job_id": job_id,
            "task_type": "initial_mask",
            "status": "completed",
            "processing_time": processing_time,
            "result": result
        }
        
        logger.info(f"Initial mask generation completed for job {job_id} in {processing_time:.2f}s")
        return final_result
        
    except Exception as e:
        error_msg = f"Initial mask generation failed for job {job_id}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Celery 표준 방식으로 실패 처리
        self.update_state(
            state="FAILURE",
            meta={
                "job_id": job_id,
                "task_type": "initial_mask",
                "error": str(e),
                "exc_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
        
        # 예외를 다시 발생시켜 Celery가 처리하도록 함
        raise


@celery_app.task(bind=True, name="propagate_3d_mask")
def propagate_3d_mask_task(
    self,
    job_id: str,
    volume_path: str,
    reference_slice: int,
    start_slice: int,
    end_slice: int,
    reference_mask_b64: str
) -> Dict[str, Any]:
    """
    3D 마스크 전파 작업
    
    Args:
        job_id: 작업 ID
        volume_path: NIfTI 파일 경로
        reference_slice: 참조 슬라이스 인덱스
        start_slice: 시작 슬라이스 인덱스
        end_slice: 끝 슬라이스 인덱스
        reference_mask_b64: Base64 인코딩된 참조 마스크
        
    Returns:
        Dict containing task result
    """
    logger.info(f"Starting 3D propagation task for job {job_id}")
    
    try:
        # 작업 상태 업데이트
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "propagation",
                "progress": 0,
                "current_operation": "Initializing 3D propagation..."
            }
        )
        
        # GPU 자원 확인
        gpu_manager = get_gpu_manager()
        if not gpu_manager.can_accept_job("propagation"):
            raise RuntimeError("Resources not available")
        
        # 진행률 콜백 함수
        def progress_callback(progress: float, operation: str):
            current_task.update_state(
                state="PROCESSING",
                meta={
                    "job_id": job_id,
                    "task_type": "propagation",
                    "progress": min(progress, 95),  # 최대 95%까지 (마지막 5%는 후처리용)
                    "current_operation": operation
                }
            )
        
        # 진행률 업데이트
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "propagation",
                "progress": 10,
                "current_operation": "Loading model and data..."
            }
        )
        
        # 추론 엔진 실행
        inference_engine = get_inference_engine()
        
        start_time = time.time()
        result = inference_engine.propagate_3d_from_mask(
            job_id=job_id,
            volume_path=volume_path,
            reference_slice=reference_slice,
            start_slice=start_slice,
            end_slice=end_slice,
            reference_mask_b64=reference_mask_b64,
            progress_callback=progress_callback
        )
        processing_time = time.time() - start_time
        
        # 최종 후처리
        current_task.update_state(
            state="PROCESSING",
            meta={
                "job_id": job_id,
                "task_type": "propagation",
                "progress": 100,
                "current_operation": "Finalizing results..."
            }
        )
        
        # 결과 파일 URL 생성
        result_file_path = result["result_file_path"]
        result_url = f"/api/v1/jobs/{job_id}/result"
        
        # 최종 결과
        final_result = {
            "job_id": job_id,
            "task_type": "propagation",
            "status": "completed",
            "processing_time": processing_time,
            "result": {
                "result_file_url": result_url,
                "result_file_path": result_file_path,  # 내부용
                "total_slices": result["total_slices"],
                "processed_slices": result["processed_slices"],
                "volume_statistics": result["volume_statistics"],
                "slice_range": result["slice_range"],
                "reference_slice": result["reference_slice"]
            }
        }
        
        logger.info(f"3D propagation completed for job {job_id} in {processing_time:.2f}s")
        return final_result
        
    except Exception as e:
        error_msg = f"3D propagation failed for job {job_id}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Celery 표준 방식으로 실패 처리
        self.update_state(
            state="FAILURE",
            meta={
                "job_id": job_id,
                "task_type": "propagation",
                "error": str(e),
                "exc_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
        
        # 예외를 다시 발생시켜 Celery가 처리하도록 함
        raise


@celery_app.task(name="cleanup_old_results")
def cleanup_old_results_task(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    오래된 결과 파일 정리 작업
    
    Args:
        max_age_hours: 최대 보관 시간 (시간)
        
    Returns:
        Dict containing cleanup results
    """
    logger.info(f"Starting cleanup task for files older than {max_age_hours} hours")
    
    try:
        import glob
        import time
        
        temp_root = os.getenv("TEMP_ROOT", "/app/temp")
        data_root = os.getenv("DATA_ROOT", "/app/data")
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        cleaned_files = []
        total_size = 0
        
        # 임시 파일 정리
        for pattern in ["*.nii.gz", "*.png", "*.jpg"]:
            files = glob.glob(os.path.join(temp_root, pattern))
            for file_path in files:
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        cleaned_files.append(file_path)
                        total_size += file_size
                        logger.info(f"Cleaned up file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean file {file_path}: {e}")
        
        # GPU 관리자 정리
        gpu_manager = get_gpu_manager()
        gpu_manager.cleanup_stale_jobs(max_age_hours)
        
        result = {
            "cleaned_files_count": len(cleaned_files),
            "total_size_mb": total_size / (1024 * 1024),
            "cleaned_files": cleaned_files[:10],  # 최대 10개만 표시
            "max_age_hours": max_age_hours
        }
        
        logger.info(f"Cleanup completed: {len(cleaned_files)} files, {total_size/(1024*1024):.2f} MB")
        return result
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise
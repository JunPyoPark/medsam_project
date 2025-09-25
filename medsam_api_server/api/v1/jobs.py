"""
범용 MedSAM2 Jobs API

파일 업로드, 2D 분할, 3D 전파, 상태 조회, 결과 다운로드
"""

import os
import uuid
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from celery.result import AsyncResult

from medsam_api_server.celery_app import celery_app
from medsam_api_server.tasks.segmentation import (
    generate_initial_mask_task,
    propagate_3d_mask_task
)
from medsam_api_server.core.gpu_manager import get_gpu_manager
from medsam_api_server.core.model_manager import MedicalImageProcessor
from medsam_api_server.schemas.api_models import (
    JobCreateResponse, InitialMaskRequest, PropagationRequest,
    JobStatusResponse, InitialMaskResponse, PropagationResponse,
    TaskStatus, TaskType, TaskProgress, MaskResult, PropagationResult,
    BaseResponse, ErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

# 환경 변수
DATA_ROOT = os.getenv("DATA_ROOT", "/app/data")
TEMP_ROOT = os.getenv("TEMP_ROOT", "/app/temp")

# 유틸리티 함수
def _job_dir(job_id: str) -> str:
    return os.path.join(DATA_ROOT, job_id)

def _volume_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "volume.nii.gz")

def _job_metadata_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "metadata.json")

def _save_job_metadata(job_id: str, metadata: Dict[str, Any]):
    """작업 메타데이터 저장"""
    metadata_path = _job_metadata_path(job_id)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

def _load_job_metadata(job_id: str) -> Optional[Dict[str, Any]]:
    """작업 메타데이터 로딩"""
    metadata_path = _job_metadata_path(job_id)
    if not os.path.exists(metadata_path):
        return None
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load metadata for job {job_id}: {e}")
        return None


@router.post("", response_model=JobCreateResponse)
async def create_job(file: UploadFile = File(...)):
    """
    새 작업 생성 및 파일 업로드
    
    NIfTI 파일(.nii.gz)을 업로드하여 새로운 작업을 생성합니다.
    """
    try:
        # 파일 검증
        if not file.filename or not file.filename.endswith(".nii.gz"):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Only .nii.gz files are supported",
                    "error_code": "INVALID_FILE_FORMAT"
                }
            )
        
        # 작업 ID 생성
        job_id = str(uuid.uuid4())
        job_path = _job_dir(job_id)
        os.makedirs(job_path, exist_ok=True)
        
        # 파일 저장
        volume_path = _volume_path(job_id)
        total_size = 0
        
        with open(volume_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                f.write(chunk)
        
        # 파일 검증 (NIfTI 로딩 테스트)
        try:
            processor = MedicalImageProcessor()
            volume_data, metadata = processor.load_nifti(volume_path)
            logger.info(f"Uploaded volume shape: {volume_data.shape}")
        except Exception as e:
            # 실패시 파일 삭제
            if os.path.exists(volume_path):
                os.remove(volume_path)
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Invalid NIfTI file: {str(e)}",
                    "error_code": "INVALID_NIFTI_FILE"
                }
            )
        
        # 작업 메타데이터 저장
        job_metadata = {
            "job_id": job_id,
            "created_at": datetime.utcnow().isoformat(),
            "file_info": {
                "filename": file.filename,
                "size_bytes": total_size,
                "content_type": file.content_type or "application/octet-stream"
            },
            "volume_info": {
                "shape": volume_data.shape,
                "spacing": metadata.get("spacing", [1.0, 1.0, 1.0]),
                "dtype": str(volume_data.dtype)
            },
            "status": TaskStatus.PENDING,
            "tasks": []
        }
        _save_job_metadata(job_id, job_metadata)
        
        logger.info(f"Created job {job_id}: {file.filename} ({total_size} bytes)")
        
        return JobCreateResponse(
            success=True,
            message="Job created successfully",
            timestamp=datetime.utcnow().isoformat(),
            job_id=job_id,
            upload_info={
                "filename": file.filename,
                "size_bytes": total_size,
                "volume_shape": volume_data.shape,
                "total_slices": volume_data.shape[0]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job creation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Job creation failed: {str(e)}",
                "error_code": "JOB_CREATION_FAILED"
            }
        )


@router.post("/{job_id}/initial-mask", response_model=InitialMaskResponse)
async def generate_initial_mask(job_id: str, request: InitialMaskRequest):
    """
    2D 초기 마스크 생성
    
    지정된 슬라이스에서 bounding box를 사용하여 초기 2D 마스크를 생성합니다.
    """
    try:
        # 작업 존재 확인
        volume_path = _volume_path(job_id)
        if not os.path.exists(volume_path):
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }
            )
        
        # GPU 자원 확인
        gpu_manager = get_gpu_manager()
        if not gpu_manager.can_accept_job("initial_mask"):
            queue_position = gpu_manager.get_queue_position(job_id)
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "message": "GPU resources not available",
                    "error_code": "GPU_BUSY",
                    "queue_position": queue_position
                }
            )
        
        # Celery 작업 시작
        task = generate_initial_mask_task.delay(
            job_id=job_id,
            volume_path=volume_path,
            slice_index=request.slice_index,
            bounding_box=[request.bounding_box.x1, request.bounding_box.y1, 
                         request.bounding_box.x2, request.bounding_box.y2],
            window_level=request.window_level
        )
        
        # 메타데이터 업데이트
        metadata = _load_job_metadata(job_id)
        if metadata:
            metadata["tasks"].append({
                "task_id": task.id,
                "task_type": "initial_mask",
                "started_at": datetime.utcnow().isoformat(),
                "request_data": request.dict()
            })
            _save_job_metadata(job_id, metadata)
        
        logger.info(f"Started initial mask generation for job {job_id}, task {task.id}")
        
        return InitialMaskResponse(
            success=True,
            message="Initial mask generation started",
            timestamp=datetime.utcnow().isoformat(),
            job_id=job_id,
            result=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Initial mask generation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Initial mask generation failed: {str(e)}",
                "error_code": "INITIAL_MASK_FAILED"
            }
        )


@router.post("/{job_id}/propagate", response_model=PropagationResponse)
async def propagate_3d_mask(job_id: str, request: PropagationRequest):
    """
    3D 마스크 전파
    
    참조 2D 마스크를 시작/끝 슬라이스까지 양방향으로 전파합니다.
    """
    try:
        # 작업 존재 확인
        volume_path = _volume_path(job_id)
        if not os.path.exists(volume_path):
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }
            )
        
        # GPU 자원 확인
        gpu_manager = get_gpu_manager()
        if not gpu_manager.can_accept_job("propagation"):
            queue_position = gpu_manager.get_queue_position(job_id)
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "message": "GPU resources not available",
                    "error_code": "GPU_BUSY",
                    "queue_position": queue_position
                }
            )
        
        # Celery 작업 시작
        task = propagate_3d_mask_task.delay(
            job_id=job_id,
            volume_path=volume_path,
            reference_slice=request.reference_slice,
            start_slice=request.start_slice,
            end_slice=request.end_slice,
            reference_mask_b64=request.mask_data
        )
        
        # 메타데이터 업데이트
        metadata = _load_job_metadata(job_id)
        if metadata:
            metadata["tasks"].append({
                "task_id": task.id,
                "task_type": "propagation",
                "started_at": datetime.utcnow().isoformat(),
                "request_data": {
                    "reference_slice": request.reference_slice,
                    "start_slice": request.start_slice,
                    "end_slice": request.end_slice
                }
            })
            _save_job_metadata(job_id, metadata)
        
        logger.info(f"Started 3D propagation for job {job_id}, task {task.id}")
        
        return PropagationResponse(
            success=True,
            message="3D propagation started",
            timestamp=datetime.utcnow().isoformat(),
            job_id=job_id,
            result=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"3D propagation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"3D propagation failed: {str(e)}",
                "error_code": "PROPAGATION_FAILED"
            }
        )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    작업 상태 조회
    
    작업의 현재 상태, 진행률, 결과 등을 조회합니다.
    """
    try:
        # 작업 존재 확인
        if not os.path.exists(_job_dir(job_id)):
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }
            )
        
        # 메타데이터 로딩
        metadata = _load_job_metadata(job_id)
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job metadata not found for {job_id}",
                    "error_code": "METADATA_NOT_FOUND"
                }
            )
        
        # 최신 작업 상태 확인
        current_status = TaskStatus.PENDING
        current_task_type = None
        progress = None
        result_url = None
        error_details = None
        
        if metadata.get("tasks"):
            # 가장 최근 작업 확인
            latest_task = metadata["tasks"][-1]
            task_id = latest_task.get("task_id")
            
            if task_id:
                task_result = AsyncResult(task_id, app=celery_app)
                current_task_type = latest_task.get("task_type")
                
                if task_result.state == "PENDING":
                    current_status = TaskStatus.PENDING
                elif task_result.state == "PROCESSING":
                    current_status = TaskStatus.PROCESSING
                    # 진행률 정보 추출
                    if task_result.info and isinstance(task_result.info, dict):
                        progress = TaskProgress(
                            current_step=task_result.info.get("progress", 0),
                            total_steps=100,
                            percentage=task_result.info.get("progress", 0),
                            current_operation=task_result.info.get("current_operation")
                        )
                elif task_result.state == "SUCCESS":
                    current_status = TaskStatus.COMPLETED
                    if current_task_type == "propagation":
                        result_url = f"/api/v1/jobs/{job_id}/result"
                elif task_result.state == "FAILURE":
                    current_status = TaskStatus.FAILED
                    # task_result.info가 dict인지 확인
                    if isinstance(task_result.info, dict):
                        error_msg = task_result.info.get("error", "Unknown error")
                    else:
                        # Exception 객체인 경우 문자열로 변환
                        error_msg = str(task_result.info) if task_result.info else "Unknown error"
                    
                    error_details = {
                        "error": error_msg,
                        "task_id": task_id
                    }
        
        # 큐 위치 확인
        gpu_manager = get_gpu_manager()
        queue_position = gpu_manager.get_queue_position(job_id)
        
        return JobStatusResponse(
            success=True,
            message="Job status retrieved successfully",
            timestamp=datetime.utcnow().isoformat(),
            job_id=job_id,
            status=current_status,
            task_type=current_task_type,
            progress=progress,
            result_url=result_url,
            error_details=error_details,
            queue_position=queue_position
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get job status: {str(e)}",
                "error_code": "STATUS_CHECK_FAILED"
            }
        )


@router.get("/{job_id}/result")
async def get_job_result(job_id: str):
    """
    작업 결과 조회
    
    2D initial mask의 경우 JSON으로 마스크 데이터 반환
    3D propagation의 경우 NIfTI 파일 다운로드
    """
    try:
        # 작업 존재 확인
        if not os.path.exists(_job_dir(job_id)):
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }
            )
        
        # 메타데이터 로딩
        metadata = _load_job_metadata(job_id)
        logger.info(f"Loaded metadata for job {job_id}: {metadata is not None}")
        if not metadata or not metadata.get("tasks"):
            logger.error(f"No tasks found for job {job_id}. Metadata: {metadata}")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "No tasks found for this job",
                    "error_code": "NO_TASKS_FOUND"
                }
            )
        
        # 가장 최근 작업 확인
        latest_task = metadata["tasks"][-1]
        task_id = latest_task.get("task_id")
        task_type = latest_task.get("task_type")
        
        logger.info(f"Latest task for job {job_id}: task_id={task_id}, task_type={task_type}")
        
        if not task_id:
            logger.error(f"Task ID not found for job {job_id}. Latest task: {latest_task}")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Task ID not found",
                    "error_code": "TASK_ID_NOT_FOUND"
                }
            )
        
        # Celery 작업 결과 확인
        task_result = AsyncResult(task_id, app=celery_app)
        
        logger.info(f"Task {task_id} ready: {task_result.ready()}, state: {task_result.state}")
        
        if not task_result.ready():
            logger.warning(f"Task {task_id} not ready yet. State: {task_result.state}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Task is not completed yet",
                    "error_code": "TASK_NOT_COMPLETED"
                }
            )
        
        if task_result.failed():
            error_info = task_result.info if task_result.info else "Unknown error"
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Task failed: {error_info}",
                    "error_code": "TASK_FAILED"
                }
            )
        
        result_data = task_result.result
        
        # 2D initial mask의 경우 JSON 반환
        if task_type == "initial_mask":
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Initial mask result retrieved successfully",
                    "timestamp": datetime.now().isoformat(),
                    "job_id": job_id,
                    "task_id": task_id,
                    "result": result_data.get("result", {})
                }
            )
        
        # 3D propagation의 경우 파일 다운로드
        elif task_type == "propagation":
            result_path = os.path.join(TEMP_ROOT, f"{job_id}_result.nii.gz")
            
            if not os.path.exists(result_path):
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "message": "Result file not found",
                        "error_code": "RESULT_NOT_FOUND"
                    }
                )
            
            return FileResponse(
                path=result_path,
                filename=f"medsam2_result_{job_id}.nii.gz",
                media_type="application/octet-stream"
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Unknown task type: {task_type}",
                    "error_code": "UNKNOWN_TASK_TYPE"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Failed to get result for job {job_id}: {e}")
        logger.error(f"Full traceback: {error_details}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get result: {str(e)}",
                "error_code": "RESULT_RETRIEVAL_FAILED",
                "debug_info": error_details
            }
        )


@router.delete("/{job_id}")
async def delete_job(job_id: str, background_tasks: BackgroundTasks):
    """
    작업 삭제
    
    작업과 관련된 모든 파일을 삭제합니다.
    """
    try:
        job_path = _job_dir(job_id)
        
        if not os.path.exists(job_path):
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Job {job_id} not found",
                    "error_code": "JOB_NOT_FOUND"
                }
            )
        
        # 백그라운드에서 파일 삭제
        def cleanup_files():
            try:
                import shutil
                # 작업 디렉토리 삭제
                if os.path.exists(job_path):
                    shutil.rmtree(job_path)
                
                # 결과 파일 삭제
                result_path = os.path.join(TEMP_ROOT, f"{job_id}_result.nii.gz")
                if os.path.exists(result_path):
                    os.remove(result_path)
                
                logger.info(f"Cleaned up files for job {job_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup files for job {job_id}: {e}")
        
        background_tasks.add_task(cleanup_files)
        
        return BaseResponse(
            success=True,
            message=f"Job {job_id} deletion scheduled",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to delete job: {str(e)}",
                "error_code": "DELETE_FAILED"
            }
        )
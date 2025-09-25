"""
시스템 모니터링 API

GPU 상태, 작업 큐, 시스템 리소스 모니터링 엔드포인트
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import List

from medsam_api_server.core.gpu_manager import get_gpu_manager
from medsam_api_server.core.model_manager import get_model_manager
from medsam_api_server.schemas.api_models import (
    BaseResponse, SystemInfo, GPUInfo, JobInfo
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status", response_model=BaseResponse)
async def get_system_status():
    """시스템 전체 상태 조회"""
    try:
        gpu_manager = get_gpu_manager()
        system_info = gpu_manager.get_system_info()
        
        # GPU 정보 변환
        gpu_info = None
        if system_info.get("gpu"):
            gpu_data = system_info["gpu"]
            gpu_info = GPUInfo(
                memory_used_mb=gpu_data["memory_used_mb"],
                memory_total_mb=gpu_data["memory_total_mb"],
                memory_percent=gpu_data["memory_percent"],
                temperature=gpu_data["temperature"],
                utilization=gpu_data["utilization"],
                is_available=gpu_data["is_available"]
            )
        
        system_info_model = SystemInfo(
            cpu_percent=system_info["cpu_percent"],
            memory=system_info["memory"],
            active_jobs=system_info["active_jobs"],
            max_concurrent_jobs=system_info["max_concurrent_jobs"],
            gpu_available=system_info["gpu_available"],
            gpu_count=system_info["gpu_count"],
            gpu=gpu_info
        )
        
        return BaseResponse(
            success=True,
            message="System status retrieved successfully",
            timestamp=datetime.utcnow().isoformat(),
            **{"system_info": system_info_model}
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get system status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/gpu", response_model=BaseResponse)
async def get_gpu_status():
    """GPU 상태 조회"""
    try:
        gpu_manager = get_gpu_manager()
        gpu_status = gpu_manager.get_gpu_status()
        
        if not gpu_status:
            return BaseResponse(
                success=True,
                message="GPU not available",
                timestamp=datetime.utcnow().isoformat(),
                **{"gpu_status": None}
            )
        
        gpu_info = GPUInfo(
            memory_used_mb=gpu_status.memory_used,
            memory_total_mb=gpu_status.memory_total,
            memory_percent=gpu_status.memory_percent,
            temperature=gpu_status.temperature,
            utilization=gpu_status.utilization,
            is_available=gpu_status.is_available
        )
        
        return BaseResponse(
            success=True,
            message="GPU status retrieved successfully",
            timestamp=datetime.utcnow().isoformat(),
            **{"gpu_status": gpu_info}
        )
        
    except Exception as e:
        logger.error(f"Failed to get GPU status: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get GPU status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/jobs/active")
async def get_active_jobs():
    """활성 작업 목록 조회"""
    try:
        gpu_manager = get_gpu_manager()
        active_jobs = gpu_manager.get_active_jobs()
        
        jobs_info = []
        for job in active_jobs:
            jobs_info.append({
                "job_id": job.job_id,
                "task_type": job.task_type,
                "start_time": job.start_time,
                "estimated_duration": job.estimated_duration,
                "memory_requirement": job.memory_requirement,
                "elapsed_time": datetime.utcnow().timestamp() - job.start_time
            })
        
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(active_jobs)} active jobs",
            timestamp=datetime.utcnow().isoformat(),
            **{
                "active_jobs": jobs_info,
                "total_count": len(active_jobs)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get active jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get active jobs: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/model", response_model=BaseResponse)
async def get_model_status():
    """모델 상태 조회"""
    try:
        model_manager = get_model_manager()
        model_info = model_manager.get_model_info()
        
        return BaseResponse(
            success=True,
            message="Model status retrieved successfully",
            timestamp=datetime.utcnow().isoformat(),
            **{"model_info": model_info}
        )
        
    except Exception as e:
        logger.error(f"Failed to get model status: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to get model status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/model/reload")
async def reload_model():
    """모델 재로딩"""
    try:
        model_manager = get_model_manager()
        model_manager.load_model(force_reload=True)
        
        return BaseResponse(
            success=True,
            message="Model reloaded successfully",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to reload model: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to reload model: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/cleanup")
async def cleanup_system():
    """시스템 정리 (오래된 작업 등)"""
    try:
        gpu_manager = get_gpu_manager()
        gpu_manager.cleanup_stale_jobs()
        
        return BaseResponse(
            success=True,
            message="System cleanup completed",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup system: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to cleanup system: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        ) 
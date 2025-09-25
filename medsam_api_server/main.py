import os
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medsam_api_server.api.v1 import jobs, system
from medsam_api_server.core.gpu_manager import get_gpu_manager
from medsam_api_server.core.model_manager import get_model_manager
from medsam_api_server.schemas.api_models import HealthResponse, SystemInfo

# 서버 시작 시간 기록
SERVER_START_TIME = time.time()

app = FastAPI(
    title="MedSAM2 GPU Service",
    description="범용 MedSAM2 3D 의료영상 분할 GPU 서비스",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
origins = [
    os.getenv("CORS_ORIGIN", "*")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(jobs.router)
app.include_router(system.router)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "MedSAM2 GPU Service",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스체크 엔드포인트"""
    try:
        # GPU 관리자 상태
        gpu_manager = get_gpu_manager()
        system_info = gpu_manager.get_system_info()
        
        # 모델 관리자 상태
        model_manager = get_model_manager()
        model_info = model_manager.get_model_info()
        
        # 시스템 정보 구성
        system_info_model = SystemInfo(
            cpu_percent=system_info["cpu_percent"],
            memory=system_info["memory"],
            active_jobs=system_info["active_jobs"],
            max_concurrent_jobs=system_info["max_concurrent_jobs"],
            gpu_available=system_info["gpu_available"],
            gpu_count=system_info["gpu_count"],
            gpu=system_info.get("gpu")
        )
        
        uptime = time.time() - SERVER_START_TIME
        
        return HealthResponse(
            success=True,
            message="Service is healthy",
            timestamp=datetime.utcnow().isoformat(),
            system_info=system_info_model,
            model_info=model_info,
            uptime=uptime
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 예외 처리"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "details": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else None
        }
    )


# 서버 시작시 초기화
@app.on_event("startup")
async def startup_event():
    """서버 시작시 실행"""
    print("🚀 MedSAM2 GPU Service starting...")
    
    # GPU 관리자 초기화
    gpu_manager = get_gpu_manager()
    print(f"✅ GPU Manager initialized: {gpu_manager.gpu_count} GPUs available")
    
    # 모델 관리자 초기화 (실제 로딩은 첫 요청시)
    model_manager = get_model_manager()
    print(f"✅ Model Manager initialized")
    
    print("🎯 MedSAM2 GPU Service ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료시 실행"""
    print("🛑 MedSAM2 GPU Service shutting down...")
    
    # 모델 언로딩
    try:
        model_manager = get_model_manager()
        model_manager.unload_model()
        print("✅ Model unloaded")
    except Exception as e:
        print(f"⚠️ Error unloading model: {e}")
    
    print("👋 MedSAM2 GPU Service stopped")
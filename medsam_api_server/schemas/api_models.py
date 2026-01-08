"""
범용 MedSAM2 API 스키마 정의

클라이언트와 서버 간의 데이터 교환을 위한 Pydantic 모델들
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class TaskStatus(str, Enum):
    """작업 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """작업 유형"""
    INITIAL_MASK = "initial_mask"
    PROPAGATION = "propagation"


# === 기본 응답 모델 ===

class BaseResponse(BaseModel):
    """기본 API 응답"""
    success: bool
    message: Optional[str] = None
    timestamp: Optional[str] = None


class ErrorResponse(BaseResponse):
    """에러 응답"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# === 작업 관련 모델 ===

class JobCreateResponse(BaseResponse):
    """작업 생성 응답"""
    job_id: str
    upload_info: Dict[str, Any]


class BoundingBox(BaseModel):
    """Bounding Box 좌표"""
    x1: int = Field(..., ge=0, description="왼쪽 상단 X 좌표")
    y1: int = Field(..., ge=0, description="왼쪽 상단 Y 좌표")
    x2: int = Field(..., gt=0, description="오른쪽 하단 X 좌표")
    y2: int = Field(..., gt=0, description="오른쪽 하단 Y 좌표")
    
    @validator('x2')
    def x2_must_be_greater_than_x1(cls, v, values):
        if 'x1' in values and v <= values['x1']:
            raise ValueError('x2 must be greater than x1')
        return v
    
    @validator('y2')
    def y2_must_be_greater_than_y1(cls, v, values):
        if 'y1' in values and v <= values['y1']:
            raise ValueError('y2 must be greater than y1')
        return v


class InitialMaskRequest(BaseModel):
    """초기 마스크 생성 요청"""
    slice_index: int = Field(..., ge=0, description="대상 슬라이스 인덱스")
    bounding_box: BoundingBox = Field(..., description="Bounding box 좌표")
    window_level: Optional[List[float]] = Field(None, description="윈도우 레벨 [window, level]")
    
    @validator('window_level')
    def validate_window_level(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError('window_level must be a list of 2 values [window, level]')
        return v


class PropagationRequest(BaseModel):
    """3D 전파 요청"""
    reference_slice: int = Field(..., ge=0, description="참조 슬라이스 인덱스")
    start_slice: int = Field(..., ge=0, description="시작 슬라이스 인덱스")
    end_slice: int = Field(..., ge=0, description="끝 슬라이스 인덱스")
    mask_data: str = Field(..., description="Base64 인코딩된 2D 마스크 데이터")
    window_level: Optional[List[float]] = Field(None, description="윈도우 레벨 [window, level]")
    
    @validator('window_level')
    def validate_window_level(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError('window_level must be a list of 2 values [window, level]')
        return v
    
    @validator('end_slice')
    def end_slice_must_be_greater_than_start(cls, v, values):
        if 'start_slice' in values and v <= values['start_slice']:
            raise ValueError('end_slice must be greater than start_slice')
        return v
    
    @validator('reference_slice')
    def reference_slice_must_be_in_range(cls, v, values):
        if 'start_slice' in values and 'end_slice' in values:
            if not (values['start_slice'] <= v <= values['end_slice']):
                raise ValueError('reference_slice must be between start_slice and end_slice')
        return v


# === 작업 상태 및 결과 모델 ===

class TaskProgress(BaseModel):
    """작업 진행률"""
    current_step: int = Field(..., ge=0)
    total_steps: int = Field(..., gt=0)
    percentage: float = Field(..., ge=0, le=100)
    estimated_remaining_time: Optional[float] = None  # seconds
    current_operation: Optional[str] = None


class JobStatusResponse(BaseResponse):
    """작업 상태 응답"""
    job_id: str
    status: TaskStatus
    task_type: Optional[TaskType] = None
    progress: Optional[TaskProgress] = None
    result_url: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    queue_position: Optional[int] = None
    estimated_start_time: Optional[float] = None  # Unix timestamp


class MaskResult(BaseModel):
    """마스크 결과"""
    mask_data: str = Field(..., description="Base64 인코딩된 마스크 데이터")
    slice_index: int = Field(..., ge=0)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    processing_time: Optional[float] = None  # seconds


class InitialMaskResponse(BaseResponse):
    """초기 마스크 생성 응답"""
    job_id: str
    result: Optional[MaskResult] = None


class PropagationResult(BaseModel):
    """3D 전파 결과"""
    result_file_url: str
    total_slices: int
    processed_slices: int
    processing_time: float  # seconds
    volume_statistics: Optional[Dict[str, Any]] = None


class PropagationResponse(BaseResponse):
    """3D 전파 응답"""
    job_id: str
    result: Optional[PropagationResult] = None


# === 시스템 정보 모델 ===

class GPUInfo(BaseModel):
    """GPU 정보"""
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
    temperature: float
    utilization: float
    is_available: bool


class SystemInfo(BaseModel):
    """시스템 정보"""
    cpu_percent: float
    memory: Dict[str, Any]
    active_jobs: int
    max_concurrent_jobs: int
    gpu_available: bool
    gpu_count: int
    gpu: Optional[GPUInfo] = None


class HealthResponse(BaseResponse):
    """헬스체크 응답"""
    system_info: SystemInfo
    model_info: Dict[str, Any]
    uptime: float  # seconds


# === 파일 관련 모델 ===

class FileUploadInfo(BaseModel):
    """파일 업로드 정보"""
    filename: str
    size_bytes: int
    content_type: str
    upload_timestamp: str


class JobInfo(BaseModel):
    """작업 정보"""
    job_id: str
    created_at: str
    file_info: FileUploadInfo
    status: TaskStatus
    tasks: List[Dict[str, Any]] = []


class JobListResponse(BaseResponse):
    """작업 목록 응답"""
    jobs: List[JobInfo]
    total_count: int
    page: int
    page_size: int 
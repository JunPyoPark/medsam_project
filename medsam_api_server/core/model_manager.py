"""
MedSAM2 모델 관리 모듈

모델 로딩, 캐싱, 메모리 관리를 담당합니다.
- 모델 싱글톤 패턴으로 메모리 효율화
- GPU 메모리 관리
- 모델 상태 모니터링
"""

import os
import gc
import logging
import threading
from typing import Optional, Dict, Any
from pathlib import Path

import torch
import numpy as np
import SimpleITK as sitk

logger = logging.getLogger(__name__)


class MedSAM2ModelManager:
    """MedSAM2 모델 관리자"""
    
    def __init__(self):
        self._model: Optional[Any] = None
        self._model_lock = threading.RLock()
        self._is_loaded = False
        self._medsam2_available = False
        
                # 모델 경로 설정
        model_root = os.getenv("MODEL_ROOT", "/app/models")
        self._model_config = {
            "checkpoint_path": os.path.join(model_root, "MedSAM2_latest.pt"),
            "config_path": "/app/MedSAM2/sam2/configs/sam2.1_hiera_t512.yaml",  # MedSAM2 내부 설정 파일 사용
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        }

        # 백업 설정 파일 경로들
        backup_configs = [
            os.path.join(model_root, "sam2.1_hiera_t512.yaml"),
            "/app/MedSAM2/sam2/configs/sam2.1_hiera_t512.yaml"
        ]
        
        # 설정 파일이 없으면 백업 경로에서 찾기
        if not os.path.exists(self._model_config["config_path"]):
            for backup_config in backup_configs:
                if os.path.exists(backup_config):
                    self._model_config["config_path"] = backup_config
                    break
        
        # MedSAM2 사용 가능 여부 확인
        try:
            from sam2.build_sam import build_sam2_video_predictor_npz
            self._medsam2_available = True
            logger.info("✅ MedSAM2 import successful")
        except ImportError as e:
            self._medsam2_available = False
            logger.warning(f"⚠️ MedSAM2 not available: {e}")
            logger.info("Server will start in limited mode (no inference capability)")
        
        # 모델 파라미터 검증
        self._validate_model_files()
    
    def _validate_model_files(self):
        """모델 파일 존재 여부 확인"""
        checkpoint_path = Path(self._model_config["checkpoint_path"])
        config_path = Path(self._model_config["config_path"])
        
        if not checkpoint_path.exists():
            logger.warning(f"Model checkpoint not found: {checkpoint_path}")
            logger.info("Please download MedSAM2 checkpoint to enable inference")
        
        if not config_path.exists():
            logger.warning(f"Model config not found: {config_path}")
            logger.info("Please ensure MedSAM2 config file is available")
        else:
            logger.info(f"Model config found: {config_path}")
        
        if checkpoint_path.exists():
            logger.info(f"Model checkpoint found: {checkpoint_path}")
    
    def load_model(self, force_reload: bool = False) -> Any:
        """모델 로딩 (싱글톤 패턴)"""
        with self._model_lock:
            if self._model is not None and self._is_loaded and not force_reload:
                return self._model
            
            if not self._medsam2_available:
                raise RuntimeError("MedSAM2 not available. Please install MedSAM2 first.")
            
            try:
                logger.info("Loading MedSAM2 model...")
                
                # 체크포인트 파일 확인
                checkpoint_path = Path(self._model_config["checkpoint_path"])
                if not checkpoint_path.exists():
                    raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")
                
                # GPU 메모리 정리
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    gc.collect()
                
                # MedSAM2 모델 로딩 - SAM2ImagePredictor 사용 (더 간단함)
                import os
                import sys
                
                # MedSAM2 경로를 Python path에 추가
                medsam2_path = "/app/MedSAM2"
                if medsam2_path not in sys.path:
                    sys.path.insert(0, medsam2_path)
                
                # MedSAM2 모델 로딩 - 올바른 Hydra 초기화
                from hydra import initialize_config_dir, compose
                from hydra.core.global_hydra import GlobalHydra
                
                # 현재 작업 디렉토리를 MedSAM2로 변경
                original_cwd = os.getcwd()
                os.chdir(medsam2_path)
                
                try:
                    # 기존 Hydra 인스턴스 정리
                    GlobalHydra.instance().clear()
                    
                    # 절대 경로로 설정 디렉토리 지정
                    config_dir = os.path.abspath("sam2/configs")
                    logger.info(f"Using config directory: {config_dir}")
                    
                    with initialize_config_dir(config_dir=config_dir, version_base=None):
                        from sam2.build_sam import build_sam2
                        from sam2.sam2_image_predictor import SAM2ImagePredictor
                        
                        logger.info("Building MedSAM2 base model...")
                        sam2_model = build_sam2(
                            config_file="sam2.1_hiera_t512",
                            ckpt_path=self._model_config["checkpoint_path"],
                            device=self._model_config["device"]
                        )
                        
                        # SAM2ImagePredictor로 래핑 (2D 분할용)
                        self._model = SAM2ImagePredictor(sam_model=sam2_model)
                        
                        # SAM2VideoPredictor도 로드 (3D propagation용)
                        from sam2.build_sam import build_sam2_video_predictor
                        self._video_model = build_sam2_video_predictor(
                            config_file="sam2.1_hiera_t512",
                            ckpt_path=self._model_config["checkpoint_path"],
                            device=self._model_config["device"]
                        )
                        
                        logger.info("✅ MedSAM2 image predictor loaded successfully!")
                        logger.info("✅ MedSAM2 video predictor loaded successfully!")
                        logger.info(f"Image model type: {type(self._model)}")
                        logger.info(f"Video model type: {type(self._video_model)}")
                        
                finally:
                    # 원래 작업 디렉토리로 복원
                    os.chdir(original_cwd)
                
                self._is_loaded = True
                logger.info(f"MedSAM2 model loaded successfully on {self._model_config['device']}")
                
                # GPU 메모리 사용량 로깅
                if torch.cuda.is_available():
                    memory_used = torch.cuda.memory_allocated() / 1024 / 1024  # MB
                    logger.info(f"GPU memory used after model loading: {memory_used:.2f} MB")
                
                return self._model
                
            except Exception as e:
                logger.error(f"Failed to load MedSAM2 model: {e}")
                self._model = None
                self._is_loaded = False
                raise RuntimeError(f"Failed to load MedSAM2 model: {e}")
    
    def unload_model(self):
        """모델 언로딩 및 메모리 정리"""
        with self._model_lock:
            if self._model is not None:
                logger.info("Unloading MedSAM2 models...")
                del self._model
                self._model = None
                
                # Video model도 언로딩
                if hasattr(self, '_video_model') and self._video_model is not None:
                    del self._video_model
                    self._video_model = None
                
                self._is_loaded = False
                
                # 메모리 정리
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    memory_used = torch.cuda.memory_allocated() / 1024 / 1024  # MB
                    logger.info(f"GPU memory used after model unloading: {memory_used:.2f} MB")
    
    def is_loaded(self) -> bool:
        """모델 로딩 상태 확인"""
        return self._is_loaded and self._model is not None
    
    def is_available(self) -> bool:
        """MedSAM2 사용 가능 여부 확인"""
        return self._medsam2_available
    
    def get_model(self) -> Any:
        """이미지 모델 인스턴스 반환 (자동 로딩)"""
        if not self.is_loaded():
            return self.load_model()
        return self._model
    
    def get_video_model(self) -> Any:
        """비디오 모델 인스턴스 반환 (3D propagation용)"""
        if not self.is_loaded():
            self.load_model()
        return getattr(self, '_video_model', None)
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        checkpoint_exists = os.path.exists(self._model_config["checkpoint_path"])
        config_exists = os.path.exists(self._model_config["config_path"])
        
        return {
            "is_loaded": self.is_loaded(),
            "is_available": self.is_available(),
            "device": self._model_config["device"],
            "checkpoint_path": self._model_config["checkpoint_path"],
            "checkpoint_exists": checkpoint_exists,
            "config_path": self._model_config["config_path"],
            "config_exists": config_exists,
            "cuda_available": torch.cuda.is_available(),
            "gpu_memory_allocated": torch.cuda.memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0,
            "gpu_memory_cached": torch.cuda.memory_reserved() / 1024 / 1024 if torch.cuda.is_available() else 0
        }


class MedicalImageProcessor:
    """의료 영상 전처리 유틸리티"""
    
    @staticmethod
    def load_nifti(file_path: str) -> tuple[np.ndarray, Dict]:
        """NIfTI 파일 로딩"""
        try:
            sitk_image = sitk.ReadImage(file_path)
            image_array = sitk.GetArrayFromImage(sitk_image)
            
            metadata = {
                "spacing": sitk_image.GetSpacing(),
                "origin": sitk_image.GetOrigin(),
                "direction": sitk_image.GetDirection(),
                "shape": image_array.shape,
                "dtype": str(image_array.dtype)
            }
            
            logger.info(f"Loaded NIfTI: {file_path}, shape: {image_array.shape}")
            return image_array, metadata
            
        except Exception as e:
            logger.error(f"Failed to load NIfTI file {file_path}: {e}")
            raise RuntimeError(f"Failed to load NIfTI file: {e}")
    
    @staticmethod
    def save_nifti(image_array: np.ndarray, file_path: str, reference_metadata: Dict = None):
        """NIfTI 파일 저장"""
        try:
            sitk_image = sitk.GetImageFromArray(image_array)
            
            if reference_metadata:
                sitk_image.SetSpacing(reference_metadata.get("spacing", (1.0, 1.0, 1.0)))
                sitk_image.SetOrigin(reference_metadata.get("origin", (0.0, 0.0, 0.0)))
                sitk_image.SetDirection(reference_metadata.get("direction", (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)))
            
            sitk.WriteImage(sitk_image, file_path)
            logger.info(f"Saved NIfTI: {file_path}, shape: {image_array.shape}")
            
        except Exception as e:
            logger.error(f"Failed to save NIfTI file {file_path}: {e}")
            raise RuntimeError(f"Failed to save NIfTI file: {e}")
    
    @staticmethod
    def normalize_image(image: np.ndarray, window_level: Optional[tuple] = None) -> np.ndarray:
        """영상 정규화"""
        if window_level:
            window, level = window_level
            min_val = level - window / 2
            max_val = level + window / 2
            image = np.clip(image, min_val, max_val)
        
        # 0-255 범위로 정규화
        image = image.astype(np.float32)
        if image.max() > image.min():
            image = (image - image.min()) / (image.max() - image.min()) * 255.0
        
        return image.astype(np.uint8)
    
    @staticmethod
    def validate_bounding_box(bbox: list, image_shape: tuple) -> bool:
        """Bounding box 유효성 검사"""
        if len(bbox) != 4:
            return False
        
        x1, y1, x2, y2 = bbox
        height, width = image_shape[-2:]  # 마지막 두 차원이 H, W
        
        return (
            0 <= x1 < x2 <= width and
            0 <= y1 < y2 <= height
        )
    
    @staticmethod
    def validate_slice_range(start_slice: int, end_slice: int, total_slices: int) -> bool:
        """슬라이스 범위 유효성 검사"""
        return (
            0 <= start_slice < end_slice < total_slices
        )


# 전역 모델 매니저 인스턴스
_model_manager: Optional[MedSAM2ModelManager] = None


def get_model_manager() -> MedSAM2ModelManager:
    """모델 매니저 싱글톤 인스턴스 반환"""
    global _model_manager
    if _model_manager is None:
        _model_manager = MedSAM2ModelManager()
    return _model_manager 
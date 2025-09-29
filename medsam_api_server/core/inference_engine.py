"""
MedSAM2 추론 엔진

실제 MedSAM2 모델을 사용한 2D 분할 및 3D 전파 로직
"""

import os
import gc
import base64
import logging
import numpy as np
from io import BytesIO
from typing import Tuple, Optional, Dict, Any, List
from PIL import Image
import torch

from medsam_api_server.core.model_manager import get_model_manager, MedicalImageProcessor
from medsam_api_server.core.gpu_manager import get_gpu_manager

logger = logging.getLogger(__name__)


def resize_grayscale_to_rgb_and_resize(array, image_size=512):
    """
    MedSAM2용 이미지 전처리: 3D grayscale을 RGB로 변환 및 리사이즈
    
    Parameters:
        array (np.ndarray): Input array of shape (d, h, w).
        image_size (int): Desired size for the width and height.
    
    Returns:
        np.ndarray: Resized array of shape (d, 3, image_size, image_size).
    """
    d, h, w = array.shape
    resized_array = np.zeros((d, 3, image_size, image_size))
    
    for i in range(d):
        img_pil = Image.fromarray(array[i].astype(np.uint8))
        img_rgb = img_pil.convert("RGB")
        img_resized = img_rgb.resize((image_size, image_size))
        img_array = np.array(img_resized).transpose(2, 0, 1)  # (3, image_size, image_size)
        resized_array[i] = img_array
    
    return resized_array


def get_largest_connected_component(mask):
    """최대 연결 성분 추출"""
    from skimage import measure
    
    if np.max(mask) == 0:
        return mask
    
    labeled = measure.label(mask)
    regions = measure.regionprops(labeled)
    
    if not regions:
        return mask
    
    # 가장 큰 영역 찾기
    largest_region = max(regions, key=lambda x: x.area)
    largest_mask = (labeled == largest_region.label).astype(np.uint8)
    
    return largest_mask


class MedSAM2InferenceEngine:
    """MedSAM2 추론 엔진"""
    
    def __init__(self):
        self.model_manager = get_model_manager()
        self.gpu_manager = get_gpu_manager()
        self.processor = MedicalImageProcessor()
        
        # MedSAM2 전용 설정
        self.image_size = 512
        self.img_mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32)
        self.img_std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32)
        
        if torch.cuda.is_available():
            self.img_mean = self.img_mean[:, None, None].cuda()
            self.img_std = self.img_std[:, None, None].cuda()
    
    def generate_initial_mask(
        self,
        job_id: str,
        volume_path: str,
        slice_index: int,
        bounding_box: List[int],
        window_level: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        2D 초기 마스크 생성
        
        Args:
            job_id: 작업 ID
            volume_path: NIfTI 파일 경로
            slice_index: 대상 슬라이스 인덱스
            bounding_box: [x1, y1, x2, y2] 좌표
            window_level: [window, level] 윈도우 레벨
            
        Returns:
            Dict containing mask data and metadata
        """
        logger.info(f"Starting initial mask generation for job {job_id}")
        
        with self.gpu_manager.acquire_gpu(job_id, "initial_mask", estimated_duration=30):
            try:
                # 1. 볼륨 데이터 로딩
                volume_data, metadata = self.processor.load_nifti(volume_path)
                logger.info(f"Loaded volume: {volume_data.shape}")
                
                # 2. 슬라이스 검증
                if slice_index >= volume_data.shape[0]:
                    raise ValueError(f"Slice index {slice_index} out of range (max: {volume_data.shape[0]-1})")
                
                # 3. 대상 슬라이스 추출
                target_slice = volume_data[slice_index]
                
                # 4. 이미지 전처리 (MedSAM2 방식)
                if window_level:
                    window, level = window_level
                    min_val = level - window / 2
                    max_val = level + window / 2
                    processed_slice = np.clip(target_slice, min_val, max_val)
                else:
                    processed_slice = target_slice.copy()
                
                # 0-255 정규화
                processed_slice = (processed_slice - np.min(processed_slice)) / (np.max(processed_slice) - np.min(processed_slice)) * 255.0
                processed_slice = np.uint8(processed_slice)
                
                # 5. Bounding box 검증
                if not self.processor.validate_bounding_box(bounding_box, processed_slice.shape):
                    raise ValueError(f"Invalid bounding box: {bounding_box}")
                
                # 6. MedSAM2 추론 (단일 슬라이스)
                model = self.model_manager.get_model()
                mask = self._run_single_slice_inference(
                    model, 
                    processed_slice, 
                    bounding_box
                )
                
                # 7. 결과 인코딩
                mask_b64 = self._encode_mask_to_base64(mask)
                
                # 8. 메타데이터 수집
                result = {
                    "mask_data": mask_b64,
                    "slice_index": slice_index,
                    "original_shape": target_slice.shape,
                    "bounding_box": bounding_box,
                    "window_level": window_level,
                    "volume_metadata": metadata
                }
                
                logger.info(f"Initial mask generation completed for job {job_id}")
                return result
                
            except Exception as e:
                logger.error(f"Initial mask generation failed for job {job_id}: {e}")
                raise
            finally:
                # GPU 메모리 정리
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
    
    def propagate_3d_from_mask(self, job_id: str, volume_path: str, reference_slice: int, 
                              start_slice: int, end_slice: int, reference_mask_b64: str,
                              progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """2D 마스크로부터 3D 전파 실행 (MedSAM2 Video Predictor 원본 방식)"""
        try:
            logger.info(f"Starting 3D propagation from mask for job {job_id}")
            logger.info(f"Reference slice: {reference_slice}, Range: {start_slice}-{end_slice}")
            
            # 1. NIfTI 파일 로딩
            processor = MedicalImageProcessor()
            volume, metadata = processor.load_nifti(volume_path)
            logger.info(f"Loaded volume: {volume.shape}")
            
            # 2. Video model 로딩
            model = self.model_manager.get_model()  # Video Predictor 통합 사용
            if model is None:
                raise RuntimeError("Video model not available for 3D propagation")
            
            # 3. 참조 마스크 디코딩 및 bbox 추출
            import base64
            from PIL import Image
            import io
            
            mask_bytes = base64.b64decode(reference_mask_b64)
            mask_img = Image.open(io.BytesIO(mask_bytes))
            reference_mask = np.array(mask_img) > 0
            logger.info(f"Reference mask shape: {reference_mask.shape}")
            
            # 참조 마스크에서 bbox 추출
            bbox = self._extract_bbox_from_mask(reference_mask)
            if bbox is None:
                raise ValueError("No valid bounding box found in reference mask")
            
            logger.info(f"Extracted bbox: {bbox}")
            
            # 4. 볼륨 전처리 (MedSAM2 원본 방식)
            # DICOM windowing (1-99 percentile 사용)
            volume_clipped = np.clip(volume, np.percentile(volume, 1), np.percentile(volume, 99))
            volume_normalized = (volume_clipped - np.min(volume_clipped)) / (np.max(volume_clipped) - np.min(volume_clipped)) * 255.0
            volume_uint8 = np.uint8(volume_normalized)
            
            logger.info(f"Volume preprocessing completed. Shape: {volume_uint8.shape}")
            
            # 5. RGB 변환 및 리사이즈
            img_resized = resize_grayscale_to_rgb_and_resize(volume_uint8, self.image_size)
            img_resized = img_resized / 255.0
            img_tensor = torch.from_numpy(img_resized).float()
            
            if torch.cuda.is_available():
                img_tensor = img_tensor.cuda()
            
            # 6. 정규화
            img_tensor -= self.img_mean
            img_tensor /= self.img_std
            
            # 7. Bounding box 좌표 변환 (원본 → 리사이즈된 이미지)
            original_h, original_w = volume.shape[1], volume.shape[2]
            video_height, video_width = original_h, original_w
            scale_x = self.image_size / original_w
            scale_y = self.image_size / original_h
            
            scaled_bbox = np.array([
                bbox[0] * scale_x,  # x_min
                bbox[1] * scale_y,  # y_min
                bbox[2] * scale_x,  # x_max
                bbox[3] * scale_y   # y_max
            ])
            
            logger.info(f"Scaled bbox: {scaled_bbox}")
            
            # 8. 결과 마스크 초기화
            mask_3d = np.zeros(volume.shape, dtype=np.uint8)
            
            # 9. MedSAM2 Video Predictor로 3D 전파 (원본 스크립트 방식)
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                # 상태 초기화
                inference_state = model.init_state(img_tensor, video_height, video_width)
                if progress_callback:
                    progress_callback(10, "MedSAM2 상태 초기화 완료")
                
                # 참조 슬라이스에 bbox 추가
                _, out_obj_ids, out_mask_logits = model.add_new_points_or_box(
                    inference_state=inference_state,
                    frame_idx=reference_slice,
                    obj_id=1,
                    box=scaled_bbox,
                )
                
                if progress_callback:
                    progress_callback(20, "참조 슬라이스 설정 완료, 순방향 전파 시작...")
                
                # Forward propagation (참조 → 끝)
                forward_count = 0
                total_forward = volume.shape[0] - reference_slice
                for out_frame_idx, out_obj_ids, out_mask_logits in model.propagate_in_video(inference_state):
                    if start_slice <= out_frame_idx <= end_slice:
                        mask = (out_mask_logits[0] > 0.0).cpu().numpy()[0]
                        mask_3d[out_frame_idx] = mask
                    
                    forward_count += 1
                    if progress_callback and total_forward > 0:
                        progress = 20 + (forward_count / total_forward) * 35
                        progress_callback(int(progress), f"순방향 전파: {out_frame_idx}/{end_slice}")
                
                # 상태 리셋 후 Backward propagation
                model.reset_state(inference_state)
                
                if progress_callback:
                    progress_callback(55, "역방향 전파 시작...")
                
                # 참조 슬라이스에 다시 bbox 추가
                _, out_obj_ids, out_mask_logits = model.add_new_points_or_box(
                    inference_state=inference_state,
                    frame_idx=reference_slice,
                    obj_id=1,
                    box=scaled_bbox,
                )
                
                # Backward propagation (참조 → 시작)
                backward_count = 0
                total_backward = reference_slice
                for out_frame_idx, out_obj_ids, out_mask_logits in model.propagate_in_video(inference_state, reverse=True):
                    if start_slice <= out_frame_idx < reference_slice:  # 중복 방지
                        mask = (out_mask_logits[0] > 0.0).cpu().numpy()[0]
                        mask_3d[out_frame_idx] = mask
                    
                    backward_count += 1
                    if progress_callback and total_backward > 0:
                        progress = 55 + (backward_count / total_backward) * 35
                        progress_callback(int(progress), f"역방향 전파: {out_frame_idx}/{start_slice}")
                
                # 상태 리셋
                model.reset_state(inference_state)
                
                if progress_callback:
                    progress_callback(90, "3D 마스크 후처리 중...")
                
                # 10. 후처리 (가장 큰 연결된 구성요소만 유지)
                if np.any(mask_3d):  # 마스크가 비어있지 않을 때만 실행
                    mask_3d = get_largest_connected_component(mask_3d)
                
                # 11. 결과 저장
                result_file_path = self._save_3d_result(job_id, mask_3d, metadata, start_slice)
                
                # 12. 통계 계산
                volume_stats = self._calculate_volume_statistics(mask_3d, metadata)
                
                if progress_callback:
                    progress_callback(100, "3D 전파 완료!")
                
                logger.info(f"3D propagation completed for job {job_id}")
                
                return {
                    "result_file_path": result_file_path,
                    "total_slices": volume.shape[0],
                    "processed_slices": end_slice - start_slice + 1,
                    "volume_statistics": volume_stats,
                    "slice_range": [start_slice, end_slice],
                    "reference_slice": reference_slice
                }
                
        except Exception as e:
            logger.error(f"3D propagation from mask failed: {e}", exc_info=True)
            raise RuntimeError(f"3D propagation from mask failed: {e}")
        finally:
            # GPU 메모리 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
    
    def _run_single_slice_inference(self, model, image: np.ndarray, bbox: List[int]) -> np.ndarray:
        """단일 슬라이스 Video Predictor 추론 (원본 MedSAM2 방식)"""
        try:
            logger.info(f"Starting single slice inference with bbox: {bbox}")
            
            # 1. 단일 슬라이스를 3D 형태로 변환 (Video Predictor는 3D 입력 필요)
            single_slice_volume = image[np.newaxis, :, :]  # (1, H, W)
            logger.info(f"Single slice volume shape: {single_slice_volume.shape}")
            
            # 2. DICOM windowing 적용 (원본 스크립트 방식)
            volume_clipped = np.clip(single_slice_volume, 
                                   np.percentile(single_slice_volume, 1), 
                                   np.percentile(single_slice_volume, 99))
            volume_normalized = (volume_clipped - np.min(volume_clipped)) / (np.max(volume_clipped) - np.min(volume_clipped)) * 255.0
            volume_uint8 = np.uint8(volume_normalized)
            
            # 3. RGB 변환 및 리사이즈 (원본 스크립트 방식)
            img_resized = resize_grayscale_to_rgb_and_resize(volume_uint8, self.image_size)
            img_resized = img_resized / 255.0
            img_tensor = torch.from_numpy(img_resized).float()
            
            if torch.cuda.is_available():
                img_tensor = img_tensor.cuda()
            
            # 4. 정규화 (ImageNet 기준)
            img_tensor -= self.img_mean
            img_tensor /= self.img_std
            
            # 5. 원본 이미지 크기 정보
            original_h, original_w = image.shape
            video_height, video_width = original_h, original_w
            
            # 6. Bounding box 좌표 변환 (원본 → 리사이즈된 이미지)
            scale_x = self.image_size / original_w
            scale_y = self.image_size / original_h
            
            scaled_bbox = np.array([
                bbox[0] * scale_x,  # x_min
                bbox[1] * scale_y,  # y_min
                bbox[2] * scale_x,  # x_max
                bbox[3] * scale_y   # y_max
            ])
            
            logger.info(f"Original bbox: {bbox}, Scaled bbox: {scaled_bbox}")
            
            # 7. Video Predictor API 사용 (원본 스크립트 방식)
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                # 상태 초기화
                inference_state = model.init_state(img_tensor, video_height, video_width)
                
                # 첫 번째 프레임(슬라이스)에 bounding box 추가
                _, out_obj_ids, out_mask_logits = model.add_new_points_or_box(
                    inference_state=inference_state,
                    frame_idx=0,  # 단일 슬라이스는 0번 프레임
                    obj_id=1,
                    box=scaled_bbox,
                )
                
                # 마스크 추출 (512x512 크기)
                mask_512 = (out_mask_logits[0] > 0.0).cpu().numpy()[0]
                mask_512 = mask_512.astype(np.uint8)
                
                # 상태 리셋
                model.reset_state(inference_state)
                
                logger.info(f"Generated mask shape: {mask_512.shape}")
                
                # 8. 원본 이미지 크기로 리사이즈
                if mask_512.shape != (original_h, original_w):
                    from PIL import Image
                    mask_pil = Image.fromarray(mask_512 * 255)
                    mask_resized_pil = mask_pil.resize((original_w, original_h), Image.NEAREST)
                    mask = (np.array(mask_resized_pil) > 128).astype(np.uint8)
                    logger.info(f"Resized mask from {mask_512.shape} to {mask.shape}")
                else:
                    mask = mask_512
                
                logger.info(f"Final mask shape: {mask.shape}, unique values: {np.unique(mask)}")
                return mask
                
        except Exception as e:
            logger.error(f"Single slice inference failed: {e}", exc_info=True)
            raise RuntimeError(f"Single slice inference failed: {e}")
    
    def _extract_bbox_from_mask(self, mask: np.ndarray) -> Optional[List[int]]:
        """마스크에서 bounding box 추출"""
        if mask.sum() == 0:
            return None
        
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        
        if not rows.any() or not cols.any():
            return None
        
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        
        return [cmin, rmin, cmax + 1, rmax + 1]
    
    def _encode_mask_to_base64(self, mask: np.ndarray) -> str:
        """마스크를 Base64로 인코딩"""
        # PNG로 저장하여 압축
        image = Image.fromarray((mask * 255).astype(np.uint8))
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Base64 인코딩
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded
    
    def _decode_mask_from_base64(self, mask_b64: str) -> np.ndarray:
        """Base64에서 마스크 디코딩"""
        # Base64 디코딩
        decoded = base64.b64decode(mask_b64)
        buffer = BytesIO(decoded)
        
        # PNG 이미지 로딩
        image = Image.open(buffer)
        mask = np.array(image)
        
        # 바이너리 마스크로 변환
        mask = (mask > 128).astype(np.uint8)
        return mask
    
    def _save_3d_result(self, job_id: str, mask_3d: np.ndarray, 
                       metadata: Dict, start_slice: int) -> str:
        """3D 결과 저장"""
        temp_root = os.getenv("TEMP_ROOT", "/app/temp")
        result_path = os.path.join(temp_root, f"{job_id}_result.nii.gz")
        
        # NIfTI로 저장
        self.processor.save_nifti(mask_3d, result_path, metadata)
        
        return result_path
    
    def _calculate_volume_statistics(self, mask_3d: np.ndarray, 
                                   metadata: Dict) -> Dict[str, Any]:
        """볼륨 통계 계산"""
        # 복셀 개수
        total_voxels = mask_3d.size
        positive_voxels = np.sum(mask_3d > 0)
        
        # 볼륨 계산 (mm³)
        spacing = metadata.get("spacing", (1.0, 1.0, 1.0))
        voxel_volume = spacing[0] * spacing[1] * spacing[2]  # mm³
        total_volume = positive_voxels * voxel_volume
        
        return {
            "total_voxels": int(total_voxels),
            "positive_voxels": int(positive_voxels),
            "volume_percentage": float(positive_voxels / total_voxels * 100) if total_voxels > 0 else 0.0,
            "volume_mm3": float(total_volume),
            "volume_ml": float(total_volume / 1000),  # ml
            "spacing": spacing,
            "shape": mask_3d.shape
        }


# 전역 추론 엔진 인스턴스
_inference_engine: Optional[MedSAM2InferenceEngine] = None


def get_inference_engine() -> MedSAM2InferenceEngine:
    """추론 엔진 싱글톤 인스턴스 반환"""
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = MedSAM2InferenceEngine()
    return _inference_engine 
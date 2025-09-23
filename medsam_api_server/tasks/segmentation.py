import os
import json
import uuid
from typing import Dict, Tuple

import numpy as np
import nibabel as nib
from celery import states
from celery.utils.log import get_task_logger
import redis

from medsam_api_server.celery_app import celery_app


LOGGER = get_task_logger(__name__)
REDIS_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
redis_client = redis.Redis.from_url(REDIS_URL)

DATA_ROOT = os.getenv("DATA_ROOT", "/home/junpyo/projects/medsam_project/data")


def _job_dir(job_id: str) -> str:
    return os.path.join(DATA_ROOT, job_id)


def _volume_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "volume.nii.gz")


def _slice_mask_path(job_id: str, slice_index: int) -> str:
    return os.path.join(_job_dir(job_id), f"slice_{slice_index:04d}_mask.npy")


def _result_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "result.nii.gz")


def _status_key(job_id: str, task_kind: str) -> str:
    return f"medsam:{job_id}:{task_kind}:status"


def _progress_key(job_id: str) -> str:
    return f"medsam:{job_id}:propagation:progress"


def _ensure_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _load_volume(job_id: str) -> Tuple[np.ndarray, nib.Nifti1Image]:
    vol_path = _volume_path(job_id)
    img = nib.load(vol_path)
    data = img.get_fdata().astype(np.float32)
    return data, img


def _save_slice_mask(job_id: str, slice_index: int, mask: np.ndarray) -> str:
    mask = (mask > 0).astype(np.uint8)
    out_path = _slice_mask_path(job_id, slice_index)
    np.save(out_path, mask)
    return out_path


@celery_app.task(bind=True, name="run_2d_segmentation")
def run_2d_segmentation(self, job_id: str, slice_index: int, box_prompt: Dict[str, int]):
    """
    Placeholder 2D segmentation: threshold pixels within bbox to create a simple mask.

    box_prompt: {"x1": int, "y1": int, "x2": int, "y2": int}
    """
    task_kind = "segment2d"
    try:
        redis_client.set(_status_key(job_id, task_kind), json.dumps({"status": "STARTED"}))
        volume, img = _load_volume(job_id)
        if slice_index < 0 or slice_index >= volume.shape[2]:
            raise ValueError("slice_index out of range")

        x1 = int(min(box_prompt["x1"], box_prompt["x2"]))
        y1 = int(min(box_prompt["y1"], box_prompt["y2"]))
        x2 = int(max(box_prompt["x1"], box_prompt["x2"]))
        y2 = int(max(box_prompt["y1"], box_prompt["y2"]))

        slice_img = volume[:, :, slice_index]
        h, w = slice_img.shape
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))

        roi = slice_img[y1:y2 + 1, x1:x2 + 1]
        if roi.size == 0:
            mask2d = np.zeros_like(slice_img, dtype=np.uint8)
        else:
            thresh = float(np.percentile(roi, 75))
            mask2d = (slice_img >= thresh).astype(np.uint8)
            # Keep only connected region overlapping with bbox center (simple heuristic)
            cy = (y1 + y2) // 2
            cx = (x1 + x2) // 2
            seed = np.zeros_like(mask2d, dtype=bool)
            seed[cy, cx] = True
            from scipy.ndimage import binary_dilation
            region = seed.copy()
            for _ in range(40):
                region = binary_dilation(region)
                region &= mask2d.astype(bool)
            mask2d = region.astype(np.uint8)

        out_path = _save_slice_mask(job_id, slice_index, mask2d)
        redis_client.set(
            _status_key(job_id, task_kind),
            json.dumps({
                "status": "COMPLETED",
                "slice_index": slice_index,
                "mask_path": out_path,
            }),
        )
        return {"mask_path": out_path}
    except Exception as e:
        LOGGER.exception("run_2d_segmentation failed")
        redis_client.set(_status_key(job_id, task_kind), json.dumps({"status": "FAILED", "error": str(e)}))
        self.update_state(state=states.FAILURE, meta={"exc": str(e)})
        raise


@celery_app.task(bind=True, name="run_3d_propagation")
def run_3d_propagation(self, job_id: str, start_slice: int, end_slice: int, initial_mask_slice_index: int):
    """
    Placeholder 3D propagation: fill between slices by simple morphological interpolation and thresholding.
    Reads the previously saved 2D mask for initial_mask_slice_index.
    """
    try:
        volume, img = _load_volume(job_id)
        z = volume.shape[2]
        start = max(0, min(start_slice, z - 1))
        end = max(0, min(end_slice, z - 1))
        if start > end:
            start, end = end, start

        init_mask_path = _slice_mask_path(job_id, initial_mask_slice_index)
        if not os.path.exists(init_mask_path):
            raise FileNotFoundError("Initial 2D mask not found. Run 2D segmentation first.")
        init_mask = np.load(init_mask_path).astype(bool)

        total = (end - start + 1)
        redis_client.set(_progress_key(job_id), json.dumps({"status": "STARTED", "progress": 0}))

        result_mask = np.zeros_like(volume, dtype=np.uint8)
        result_mask[:, :, initial_mask_slice_index] = init_mask.astype(np.uint8)

        # Simple forward/backward propagation using threshold guidance
        slice_indices = list(range(initial_mask_slice_index - 1, start - 1, -1)) + list(range(initial_mask_slice_index + 1, end + 1))
        processed = 1
        for si in slice_indices:
            base = volume[:, :, si]
            # Adaptive threshold guided by initial mask intensity stats
            masked_vals = volume[:, :, initial_mask_slice_index][init_mask]
            if masked_vals.size == 0:
                thr = float(np.percentile(base, 80))
            else:
                mu = float(np.mean(masked_vals))
                thr = max(mu * 0.8, float(np.percentile(base, 70)))
            cand = (base >= thr)
            # Smooth and keep largest connected region nearby center of previous mask
            from scipy.ndimage import binary_opening, binary_closing
            sm = binary_closing(binary_opening(cand, iterations=1), iterations=1)
            result_mask[:, :, si] = sm.astype(np.uint8)
            processed += 1
            prog = int(processed / total * 100)
            redis_client.set(_progress_key(job_id), json.dumps({"status": "PROCESSING", "progress": prog}))

        # Save as NIfTI
        out_img = nib.Nifti1Image(result_mask.astype(np.uint8), affine=img.affine, header=img.header)
        out_path = _result_path(job_id)
        nib.save(out_img, out_path)
        redis_client.set(_progress_key(job_id), json.dumps({"status": "COMPLETED", "progress": 100, "result_path": out_path}))
        return {"result_path": out_path}
    except Exception as e:
        LOGGER.exception("run_3d_propagation failed")
        redis_client.set(_progress_key(job_id), json.dumps({"status": "FAILED", "error": str(e)}))
        self.update_state(state=states.FAILURE, meta={"exc": str(e)})
        raise
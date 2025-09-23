import os
import io
import uuid
import json
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from medsam_api_server.tasks.segmentation import run_2d_segmentation, run_3d_propagation

DATA_ROOT = os.getenv("DATA_ROOT", "/home/junpyo/projects/medsam_project/data")

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _job_dir(job_id: str) -> str:
    return os.path.join(DATA_ROOT, job_id)


def _volume_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "volume.nii.gz")


def _result_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "result.nii.gz")


@router.post("")
async def create_job(file: UploadFile = File(...)):
    try:
        job_id = str(uuid.uuid4())
        job_path = _job_dir(job_id)
        os.makedirs(job_path, exist_ok=True)
        vol_path = _volume_path(job_id)

        fname = file.filename or ""
        print(f"[create_job] job_id={job_id} filename={fname} content_type={file.content_type}")
        if not fname.endswith(".nii.gz"):
            raise HTTPException(status_code=400, detail=f"Only .nii.gz files are supported (got: {fname})")

        total = 0
        with open(vol_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                f.write(chunk)
        print(f"[create_job] saved {total} bytes to {vol_path}")

        if total == 0 or not os.path.exists(vol_path):
            raise HTTPException(status_code=400, detail="Empty upload or failed to save file")

        return JSONResponse({"job_id": job_id, "status": "CREATED"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"[create_job][ERROR] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/segment-2d")
async def segment_2d(job_id: str,
                     slice_index: int = Form(...),
                     x1: int = Form(...),
                     y1: int = Form(...),
                     x2: int = Form(...),
                     y2: int = Form(...)):
    if not os.path.exists(_volume_path(job_id)):
        raise HTTPException(status_code=404, detail="job_id not found")

    box = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    task = run_2d_segmentation.delay(job_id=job_id, slice_index=slice_index, box_prompt=box)
    return JSONResponse({"status": "PROCESSING", "task_id": task.id})


@router.get("/{job_id}/status")
async def get_status(job_id: str, task_type: Optional[str] = None):
    from medsam_api_server.tasks.segmentation import redis_client, _status_key, _progress_key
    response = {"job_id": job_id}
    if task_type == "segment2d":
        st = redis_client.get(_status_key(job_id, "segment2d"))
        response.update(json.loads(st) if st else {"status": "UNKNOWN"})
        return JSONResponse(response)
    st = redis_client.get(_progress_key(job_id))
    response.update(json.loads(st) if st else {"status": "IDLE", "progress": 0})
    if response.get("status") == "COMPLETED":
        response["result_url"] = f"/api/v1/jobs/{job_id}/result"
    return JSONResponse(response)


@router.post("/{job_id}/propagate")
async def propagate(job_id: str,
                    start_slice: int = Form(...),
                    end_slice: int = Form(...),
                    initial_mask_slice_index: int = Form(...)):
    if not os.path.exists(_volume_path(job_id)):
        raise HTTPException(status_code=404, detail="job_id not found")

    task = run_3d_propagation.delay(job_id=job_id,
                                    start_slice=start_slice,
                                    end_slice=end_slice,
                                    initial_mask_slice_index=initial_mask_slice_index)
    return JSONResponse({"status": "PROCESSING", "task_id": task.id})


@router.get("/{job_id}/result")
async def download_result(job_id: str):
    path = _result_path(job_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Result not found")

    def iterfile():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(iterfile(), media_type="application/gzip", headers={
        "Content-Disposition": f"attachment; filename=mask_{job_id}.nii.gz"
    })
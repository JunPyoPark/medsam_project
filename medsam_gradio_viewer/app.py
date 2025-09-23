import os
import time
import json
import requests
import numpy as np
import nibabel as nib
import gradio as gr
from typing import Optional, Tuple

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

# Patch gradio_client JSON schema utils to handle boolean schemas
try:
    import gradio_client.utils as _gc_utils  # type: ignore

    _orig_get_type = getattr(_gc_utils, "get_type", None)
    _orig_conv = getattr(_gc_utils, "_json_schema_to_python_type", None)

    def _safe_get_type(schema):
        if isinstance(schema, bool):
            return "any"
        return _orig_get_type(schema)

    def _safe_conv(schema, defs=None):
        if isinstance(schema, bool):
            return "any"
        return _orig_conv(schema, defs)

    if _orig_get_type and _orig_conv:
        _gc_utils.get_type = _safe_get_type
        _gc_utils._json_schema_to_python_type = _safe_conv
except Exception:
    pass


def _draw_box(img: np.ndarray, x1: Optional[float], y1: Optional[float], x2: Optional[float], y2: Optional[float]) -> np.ndarray:
    if img is None:
        return None
    h, w = img.shape[:2]
    try:
        xi1 = int(max(0, min(w - 1, int(x1)))) if x1 is not None else None
        yi1 = int(max(0, min(h - 1, int(y1)))) if y1 is not None else None
        xi2 = int(max(0, min(w - 1, int(x2)))) if x2 is not None else None
        yi2 = int(max(0, min(h - 1, int(y2)))) if y2 is not None else None
        if None in (xi1, yi1, xi2, yi2):
            return img
        xa, xb = sorted([xi1, xi2])
        ya, yb = sorted([yi1, yi2])
        out = np.stack([img, img, img], axis=-1) if img.ndim == 2 else img.copy()
        color = np.array([0.0, 1.0, 0.0])
        thickness = 2
        out[ya:ya + thickness, xa:xb + 1, ...] = color
        out[yb - thickness + 1:yb + 1, xa:xb + 1, ...] = color
        out[ya:yb + 1, xa:xa + thickness, ...] = color
        out[ya:yb + 1, xb - thickness + 1:xb + 1, ...] = color
        return out
    except Exception:
        return img


def _display_to_original_xy(img_state, slice_index: int, x_disp: int, y_disp: int) -> Tuple[int, int]:
    if img_state is None:
        return int(x_disp), int(y_disp)
    _, vol = img_state
    h, w = vol[:, :, slice_index].shape
    x_orig = int(y_disp)
    y_orig = int(max(0, min(h - 1, h - 1 - int(x_disp))))
    return x_orig, y_orig


def load_nifti(fileobj):
    if fileobj is None:
        return None, None, None
    path = fileobj.name
    img = nib.load(path)
    vol = img.get_fdata().astype(np.float32)
    z = vol.shape[2]
    vmin, vmax = np.percentile(vol, [1, 99])
    vol_disp = np.clip((vol - vmin) / max(vmax - vmin, 1e-6), 0, 1)
    return vol_disp, int(z), (img, vol)


def create_job(fileobj):
    try:
        if fileobj is None:
            return None, "업로드된 파일이 없습니다.", None
        file_path = fileobj.name
        if not file_path.endswith(".nii.gz"):
            return None, f"확장자 오류: .nii.gz만 지원합니다 (현재: {os.path.basename(file_path)})", None
        print(f"[create_job] uploading: {file_path} -> {API_BASE}/api/v1/jobs")
        with open(file_path, "rb") as fh:
            files = {"file": (os.path.basename(file_path), fh, "application/gzip")}
            resp = requests.post(f"{API_BASE}/api/v1/jobs", files=files, timeout=120)
        print(f"[create_job] status={resp.status_code} body={resp.text[:200]}")
        if resp.status_code != 200:
            return None, f"Job 생성 실패: {resp.status_code} {resp.text}", None
        job_id = resp.json().get("job_id")
        if not job_id:
            return None, f"Job 생성 응답 이상: {resp.text}", None
        return job_id, f"Job 생성됨: {job_id}", job_id
    except Exception as e:
        print(f"[create_job][ERROR] {e}")
        return None, f"예외 발생: {type(e).__name__}: {e}", None


def show_slice(state, slice_index, x1=None, y1=None, x2=None, y2=None):
    if state is None:
        return None
    img, vol = state
    slice_img = vol[:, :, slice_index]
    slice_img = np.rot90(slice_img, k=-1)
    vmin, vmax = np.percentile(slice_img, [1, 99])
    disp = np.clip((slice_img - vmin) / max(vmax - vmin, 1e-6), 0, 1)
    disp = _draw_box(disp, x1, y1, x2, y2)
    return disp


def trigger_segmentation(job_id, img_state, slice_index, x1d, y1d, x2d, y2d):
    if not job_id:
        return "먼저 Job을 생성하세요."
    x1o, y1o = _display_to_original_xy(img_state, slice_index, x1d, y1d)
    x2o, y2o = _display_to_original_xy(img_state, slice_index, x2d, y2d)
    data = {"slice_index": slice_index, "x1": x1o, "y1": y1o, "x2": x2o, "y2": y2o}
    resp = requests.post(f"{API_BASE}/api/v1/jobs/{job_id}/segment-2d", data=data, timeout=10)
    if resp.status_code != 200:
        return f"요청 실패: {resp.text}"
    return "PROCESSING"


def poll_segmentation(job_id, slice_index, img_state):
    if not job_id:
        return None, "Job이 없습니다."
    for _ in range(120):
        st = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", params={"task_type": "segment2d"}, timeout=5)
        info = st.json()
        if info.get("status") == "COMPLETED" and info.get("slice_index") == slice_index:
            mask_path = info.get("mask_path")
            mask = np.load(mask_path)
            mask = np.rot90(mask, k=-1)
            base = show_slice(img_state, slice_index)
            overlay = np.stack([base, base, base], axis=-1) if base.ndim == 2 else base.copy()
            overlay[mask.astype(bool), :3] = [1.0, 0.0, 0.0]
            return overlay, "세그멘테이션 완료"
        elif info.get("status") == "FAILED":
            return None, f"실패: {info.get('error')}", None
        time.sleep(3)
    return None, "타임아웃"


def trigger_propagation(job_id, start_slice, end_slice, initial_mask_slice_index):
    if not job_id:
        return "먼저 Job을 생성하세요."
    data = {
        "start_slice": start_slice,
        "end_slice": end_slice,
        "initial_mask_slice_index": initial_mask_slice_index,
    }
    resp = requests.post(f"{API_BASE}/api/v1/jobs/{job_id}/propagate", data=data, timeout=10)
    if resp.status_code != 200:
        return f"요청 실패: {resp.text}"
    return "PROCESSING"


def poll_propagation(job_id):
    if not job_id:
        return 0, "Job이 없습니다.", None
    for _ in range(3600):
        st = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", timeout=5)
        info = st.json()
        status = info.get("status")
        prog = int(info.get("progress", 0))
        if status == "COMPLETED":
            url = info.get("result_url")
            return 100, "완료", url
        elif status == "FAILED":
            return 0, f"실패: {info.get('error')}", None
        time.sleep(3)
        yield prog, f"진행중: {prog}%", None


with gr.Blocks(title="MedSAM2 3D 뷰어") as demo:
    gr.Markdown("**MedSAM2 HITL 3D 뷰어 (NIfTI)**")
    gr.HTML("""
    <style>
      #slice_image img { user-select: none; -webkit-user-drag: none; }
    </style>
    """)
    with gr.Row():
        nifti_file = gr.File(label="NIfTI (.nii.gz) 업로드", file_types=[".nii.gz"], type="filepath")
        create_btn = gr.Button("새 작업 시작")
        job_state = gr.State()
        img_state = gr.State()
        z_state = gr.State()
        mid_state = gr.State()
        status_box = gr.Markdown()
    with gr.Row():
        slice_slider = gr.Slider(0, 0, value=0, step=1, label="슬라이스")
    with gr.Row():
        image = gr.Image(label="슬라이스", interactive=False, elem_id="slice_image")
    with gr.Accordion("2D 분할 (중간 슬라이스)", open=True):
        with gr.Row():
            x1 = gr.Number(label="x1", value=10)
            y1 = gr.Number(label="y1", value=10)
            x2 = gr.Number(label="x2", value=50)
            y2 = gr.Number(label="y2", value=50)
        with gr.Row():
            seg_mid_btn = gr.Button("중간 슬라이스 2D 분할")
        with gr.Row():
            draw_help = gr.Markdown("")
    with gr.Accordion("3D Propagation (중간→양방향)", open=True):
        with gr.Row():
            start_slice = gr.Number(label="시작 슬라이스", value=0)
            end_slice = gr.Number(label="끝 슬라이스", value=0)
            init_slice = gr.Number(label="초기 마스크 슬라이스", value=0)
            run_3d = gr.Button("3D Propagation 실행")
        result_link = gr.Markdown(visible=False)

    def on_upload(fileobj, x1v, y1v, x2v, y2v):
        vol_disp, z, state = load_nifti(fileobj)
        if vol_disp is None:
            return gr.update(), gr.update(), None, None, None
        mid = int(z // 2)
        disp_mid = np.rot90(vol_disp[:, :, mid], k=-1)
        disp_mid = _draw_box(disp_mid, x1v, y1v, x2v, y2v)
        return (
            gr.update(minimum=0, maximum=z-1, value=mid),
            gr.update(value=disp_mid),
            state,
            z,
            mid,
        )

    nifti_file.change(fn=on_upload, inputs=[nifti_file, x1, y1, x2, y2], outputs=[slice_slider, image, img_state, z_state, mid_state])

    def on_create(fileobj, z):
        job_id, msg, jobid_state = create_job(fileobj)
        return jobid_state, msg, 0, max((z or 1) - 1, 0), int((z or 1) // 2)

    create_btn.click(fn=on_create, inputs=[nifti_file, z_state], outputs=[job_state, status_box, start_slice, end_slice, init_slice])

    slice_slider.release(fn=show_slice, inputs=[img_state, slice_slider, x1, y1, x2, y2], outputs=image)

    def update_box(img_state_v, slice_index_v, x1v, y1v, x2v, y2v):
        return show_slice(img_state_v, int(slice_index_v), x1v, y1v, x2v, y2v)

    for ctrl in (x1, y1, x2, y2):
        ctrl.change(fn=update_box, inputs=[img_state, slice_slider, x1, y1, x2, y2], outputs=image)

    def seg_middle(job_id, mid, x1v, y1v, x2v, y2v, img_state_v):
        return trigger_segmentation(job_id, img_state_v, int(mid), x1v, y1v, x2v, y2v)

    seg_chain = seg_mid_btn.click(
        fn=seg_middle,
        inputs=[job_state, mid_state, x1, y1, x2, y2, img_state],
        outputs=[status_box],
    )
    seg_chain.then(fn=poll_segmentation, inputs=[job_state, mid_state, img_state], outputs=[image, status_box])

    def start_prop(job_id, s, e, init_si, mid):
        if mid is not None:
            s = 0
            e = max(int((z_state.value or 1) - 1), 0) if hasattr(z_state, 'value') else int(e)
            init_si = int(mid)
        return trigger_propagation(job_id, int(s), int(e), int(init_si))

    def poll3(job_id):
        progress = gr.Progress(track_tqdm=False)
        for prog, msg, url in poll_propagation(job_id):
            progress(prog)
        st = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", timeout=5).json()
        if st.get("status") == "COMPLETED" and st.get("result_url"):
            url = st.get("result_url")
            return gr.update(value=f"[3D 마스크 다운로드]({url})", visible=True), "완료"
        return gr.update(visible=False), "실패 또는 타임아웃"

    prop_chain = run_3d.click(fn=start_prop, inputs=[job_state, start_slice, end_slice, init_slice, mid_state], outputs=[status_box])
    prop_chain.then(fn=poll3, inputs=[job_state], outputs=[result_link, status_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True, show_api=False)
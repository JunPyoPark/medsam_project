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
    
    try:
        # 이미지가 np.rot90(k=-1)로 90도 회전되어 표시됨
        # 원본 이미지 크기 정보 가져오기
        vol_data, z_size, mid_slice = img_state
        
        # vol_data는 (z, h, w) 형태이므로 h, w는 shape[1], shape[2]
        if len(vol_data.shape) == 3:
            original_h, original_w = vol_data.shape[1], vol_data.shape[2]  # (H, W)
        else:
            # 2D 이미지인 경우
            original_h, original_w = vol_data.shape[0], vol_data.shape[1]
        
        # 회전된 이미지 크기 (np.rot90(k=-1) 후)
        rotated_h, rotated_w = original_w, original_h  # 90도 회전으로 크기 바뀜
        
        # np.rot90(k=-1) 정확한 역변환 공식
        # 원본 (i,j) -> 회전 (j, H-1-i)
        # 역변환: 회전 (x,y) -> 원본 (W-1-y, x)
        x_orig = int(rotated_w - 1 - y_disp)
        y_orig = int(x_disp)
        
        # 경계 검사
        x_orig = max(0, min(original_w - 1, x_orig))
        y_orig = max(0, min(original_h - 1, y_orig))
        
        print(f"[_display_to_original_xy] Display: ({x_disp}, {y_disp}) -> Original: ({x_orig}, {y_orig})")
        print(f"[_display_to_original_xy] Vol shape: {vol_data.shape}, Original HW: ({original_h}, {original_w})")
        print(f"[_display_to_original_xy] Rotated HW: ({rotated_h}, {rotated_w})")
        
        return x_orig, y_orig
        
    except Exception as e:
        print(f"[_display_to_original_xy] Error in coordinate transformation: {e}")
        # 에러 발생 시 기본 변환 사용
        return int(x_disp), int(y_disp)


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
    
    # 백엔드 API에 맞는 JSON 형식으로 요청
    data = {
        "slice_index": slice_index, 
        "bounding_box": {
            "x1": x1o, 
            "y1": y1o, 
            "x2": x2o, 
            "y2": y2o
        }
    }
    
    print(f"[trigger_segmentation] Sending request: {data}")
    resp = requests.post(f"{API_BASE}/api/v1/jobs/{job_id}/initial-mask", 
                        json=data, 
                        headers={"Content-Type": "application/json"},
                        timeout=30)
    
    print(f"[trigger_segmentation] Response: {resp.status_code} {resp.text}")
    if resp.status_code != 200:
        return f"요청 실패: {resp.status_code} {resp.text}"
    return "PROCESSING"


def poll_segmentation(job_id, slice_index, img_state):
    if not job_id:
        return None, "Job이 없습니다."
    
    print(f"[poll_segmentation] Polling job {job_id} for slice {slice_index}")
    
    for i in range(40):  # 40 * 3초 = 2분 대기
        try:
            # 작업 상태 확인
            st_resp = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", timeout=10)
            print(f"[poll_segmentation] Status check {i+1}: {st_resp.status_code}")
            
            if st_resp.status_code == 404:
                print(f"[poll_segmentation] Job {job_id} not found (404) - stopping polling")
                return None, "❌ 작업을 찾을 수 없습니다. 새로운 작업을 시작해주세요."
            elif st_resp.status_code != 200:
                print(f"[poll_segmentation] Status check failed: {st_resp.text}")
                time.sleep(3)
                continue
                
            info = st_resp.json()
            status = info.get("status")
            print(f"[poll_segmentation] Current status: {status}")
            
            if status == "completed":
                # 결과 가져오기
                result_resp = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/result", timeout=10)
                print(f"[poll_segmentation] Result fetch: {result_resp.status_code}")
                
                if result_resp.status_code == 200:
                    result_data = result_resp.json()
                    if result_data.get("success") and "result" in result_data:
                        # 마스크 데이터 디코딩
                        import base64
                        from PIL import Image
                        import io
                        
                        mask_b64 = result_data["result"]["mask_data"]
                        mask_bytes = base64.b64decode(mask_b64)
                        mask_img = Image.open(io.BytesIO(mask_bytes))
                        mask = np.array(mask_img) > 0  # 바이너리 마스크로 변환
                        
                        print(f"[poll_segmentation] Mask shape: {mask.shape}")
                        
                        # 원본 이미지와 오버레이
                        base = show_slice(img_state, slice_index)
                        if base is None:
                            return None, "원본 이미지를 불러올 수 없습니다."
                        
                        # RGB 변환
                        if base.ndim == 2:
                            overlay = np.stack([base, base, base], axis=-1)
                        else:
                            overlay = base.copy()
                        
                        # 마스크 크기를 원본에 맞게 조정
                        if mask.shape != base.shape[:2]:
                            from PIL import Image as PILImage
                            mask_pil = PILImage.fromarray(mask.astype(np.uint8) * 255)
                            mask_pil = mask_pil.resize((base.shape[1], base.shape[0]), PILImage.NEAREST)
                            mask = np.array(mask_pil) > 128
                        
                        # 빨간색으로 마스크 영역 표시
                        overlay[mask, 0] = 1.0  # Red channel
                        overlay[mask, 1] = 0.0  # Green channel  
                        overlay[mask, 2] = 0.0  # Blue channel
                        
                        return overlay, "✅ 세그멘테이션 완료!"
                    else:
                        return None, f"결과 데이터 오류: {result_data}"
                else:
                    return None, f"결과 가져오기 실패: {result_resp.status_code} {result_resp.text}"
                    
            elif status == "failed":
                return None, f"❌ 작업 실패: {info.get('error_details', '알 수 없는 오류')}"
            
            # 진행 중이면 계속 대기
            time.sleep(3)
            
        except Exception as e:
            print(f"[poll_segmentation] Exception: {e}")
            time.sleep(3)
    
    return None, "⏰ 타임아웃 - 작업이 너무 오래 걸립니다."


def trigger_propagation(job_id, start_slice, end_slice, initial_mask_slice_index):
    if not job_id:
        return "먼저 Job을 생성하세요."
    
    print(f"[trigger_propagation] Starting 3D propagation for job {job_id}")
    print(f"[trigger_propagation] Range: {start_slice} -> {end_slice}, reference: {initial_mask_slice_index}")
    
    # 먼저 2D 분할 결과에서 마스크 데이터를 가져오기
    try:
        result_resp = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/result", timeout=10)
        if result_resp.status_code != 200:
            return f"2D 분할 결과를 가져올 수 없습니다: {result_resp.status_code}"
        
        result_data = result_resp.json()
        if not result_data.get("success") or "result" not in result_data:
            return f"2D 분할 결과가 없습니다: {result_data}"
        
        mask_data = result_data["result"]["mask_data"]
        print(f"[trigger_propagation] Got mask data (length: {len(mask_data)})")
        
        # 3D propagation 요청
        data = {
            "start_slice": int(start_slice),
            "end_slice": int(end_slice), 
            "reference_slice": int(initial_mask_slice_index),
            "mask_data": mask_data
        }
        
        print(f"[trigger_propagation] Sending 3D propagation request...")
        resp = requests.post(f"{API_BASE}/api/v1/jobs/{job_id}/propagate", 
                            json=data,
                            headers={"Content-Type": "application/json"},
                            timeout=30)
        
        print(f"[trigger_propagation] Response: {resp.status_code} {resp.text}")
        if resp.status_code != 200:
            return f"3D 전파 요청 실패: {resp.status_code} {resp.text}"
        
        return "PROCESSING"
        
    except Exception as e:
        print(f"[trigger_propagation] Exception: {e}")
        return f"3D 전파 시작 실패: {str(e)}"


def poll_propagation(job_id):
    if not job_id:
        return 0, "Job이 없습니다.", None
    
    print(f"[poll_propagation] Starting to poll job {job_id}")
    
    for i in range(1200):  # 1200 * 3초 = 1시간 대기
        try:
            st_resp = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", timeout=10)
            if st_resp.status_code == 404:
                print(f"[poll_propagation] Job {job_id} not found (404) - stopping polling")
                yield 0, "❌ 작업을 찾을 수 없습니다. 새로운 작업을 시작해주세요.", None
                return
            elif st_resp.status_code != 200:
                print(f"[poll_propagation] Status check failed: {st_resp.text}")
                time.sleep(3)
                continue
            
            info = st_resp.json()
            status = info.get("status")
            task_type = info.get("task_type")
            
            print(f"[poll_propagation] Check {i+1}: status={status}, task_type={task_type}")
            
            # propagation 작업 상태만 확인
            if task_type == "propagation":
                if status == "completed":
                    print(f"[poll_propagation] 3D propagation completed!")
                    # 결과 파일 다운로드 URL 생성
                    download_url = f"{API_BASE}/api/v1/jobs/{job_id}/result"
                    yield 100, "✅ 3D 전파 완료!", download_url
                    return
                elif status == "failed":
                    error_msg = info.get("error_details", "알 수 없는 오류")
                    print(f"[poll_propagation] 3D propagation failed: {error_msg}")
                    yield 0, f"❌ 3D 전파 실패: {error_msg}", None
                    return
                elif status == "processing":
                    # 진행률 정보가 있으면 사용
                    progress_info = info.get("progress")
                    if progress_info and isinstance(progress_info, dict):
                        prog = progress_info.get("percentage", 0)
                        operation = progress_info.get("current_operation", "처리 중...")
                        yield prog, f"🔄 {operation} ({prog}%)", None
                    else:
                        # 기본 진행률 표시 (최대 95%까지)
                        basic_progress = min(95, 10 + (i * 0.1))  # 천천히 증가
                        yield int(basic_progress), f"🔄 3D 마스크 전파 중... ({int(basic_progress)}%)", None
                else:
                    # pending 상태
                    yield 5, "⏳ 3D 전파 작업 대기 중...", None
            else:
                # 아직 propagation 작업이 시작되지 않음
                yield 1, "⏳ 3D 전파 작업 준비 중...", None
            
            time.sleep(3)
            
        except Exception as e:
            print(f"[poll_propagation] Exception: {e}")
            time.sleep(3)
    
    # 타임아웃
    yield 0, "⏰ 3D 전파 타임아웃 - 작업이 너무 오래 걸립니다.", None


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
            x1 = gr.Number(label="x1", value=200)
            y1 = gr.Number(label="y1", value=265)
            x2 = gr.Number(label="x2", value=240)
            y2 = gr.Number(label="y2", value=310)
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
        if z is not None and z > 1:
            start_val = 0
            end_val = int(z) - 1  # 마지막 슬라이스 인덱스
            init_val = int(z // 2)  # 중간 슬라이스
        else:
            start_val = 0
            end_val = 1
            init_val = 0
        print(f"[on_create] Setting 3D propagation range: {start_val} to {end_val}, reference: {init_val}")
        return jobid_state, msg, start_val, end_val, init_val

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

    def start_prop(job_id, s, e, init_si, mid, z_total):
        # 기본값 설정: 전체 볼륨 범위 사용
        if z_total is not None and z_total > 1:
            s = 0
            e = int(z_total) - 1  # 마지막 슬라이스 인덱스
            init_si = int(mid) if mid is not None else int(z_total // 2)
        else:
            # z_total이 없는 경우 입력값 사용 (최소 검증)
            s = max(0, int(s))
            e = max(int(s) + 1, int(e))  # end_slice가 start_slice보다 최소 1 크도록
            init_si = int(init_si)
        
        print(f"[start_prop] 3D propagation: start={s}, end={e}, reference={init_si}")
        return trigger_propagation(job_id, s, e, init_si)

    def poll3(job_id):
        progress = gr.Progress(track_tqdm=False)
        for prog, msg, url in poll_propagation(job_id):
            progress(prog)
        st = requests.get(f"{API_BASE}/api/v1/jobs/{job_id}/status", timeout=5).json()
        if st.get("status") == "COMPLETED" and st.get("result_url"):
            url = st.get("result_url")
            return gr.update(value=f"[3D 마스크 다운로드]({url})", visible=True), "완료"
        return gr.update(visible=False), "실패 또는 타임아웃"

    prop_chain = run_3d.click(fn=start_prop, inputs=[job_state, start_slice, end_slice, init_slice, mid_state, z_state], outputs=[status_box])
    prop_chain.then(fn=poll3, inputs=[job_state], outputs=[result_link, status_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_api=False)
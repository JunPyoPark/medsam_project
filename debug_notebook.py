#!/usr/bin/env python3
"""
좌표 변환 대화형 디버깅
"""
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import nibabel as nib

def load_actual_image():
    """실제 NIfTI 이미지를 로드해서 테스트"""
    try:
        # 실제 업로드된 이미지 경로 찾기
        import os
        data_dir = "/tmp/gradio"
        
        # 가장 최근 업로드된 파일 찾기
        nii_files = []
        if os.path.exists(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    if file.endswith('.nii.gz'):
                        nii_files.append(os.path.join(root, file))
        
        if nii_files:
            latest_file = max(nii_files, key=os.path.getctime)
            print(f"로드된 파일: {latest_file}")
            
            # NIfTI 파일 로드
            nii = nib.load(latest_file)
            vol_data = nii.get_fdata()
            
            print(f"볼륨 shape: {vol_data.shape}")
            
            # 중간 슬라이스 선택
            mid_slice = vol_data.shape[0] // 2
            slice_img = vol_data[mid_slice, :, :]
            
            print(f"슬라이스 {mid_slice} shape: {slice_img.shape}")
            
            return slice_img, vol_data.shape
        else:
            print("NIfTI 파일을 찾을 수 없습니다.")
            return None, None
            
    except Exception as e:
        print(f"이미지 로드 실패: {e}")
        return None, None

def test_coordinate_transforms():
    """다양한 좌표 변환 방법 테스트"""
    
    # 실제 이미지 로드 시도
    slice_img, vol_shape = load_actual_image()
    
    if slice_img is not None:
        original_h, original_w = slice_img.shape
        print(f"실제 이미지 크기: {original_h} x {original_w}")
    else:
        # 기본값 사용
        original_h, original_w = 480, 480
        slice_img = np.random.rand(original_h, original_w)
        print(f"테스트 이미지 크기: {original_h} x {original_w}")
    
    # Gradio에서 표시되는 방식으로 회전
    rotated_img = np.rot90(slice_img, k=-1)
    rotated_h, rotated_w = rotated_img.shape
    
    print(f"회전된 이미지 크기: {rotated_h} x {rotated_w}")
    
    # 사용자가 선택한 좌표 (bounding box)
    user_coords = [(200, 265), (240, 310)]  # x1,y1, x2,y2
    
    print("\n=== 좌표 변환 비교 ===")
    
    for i, (x_disp, y_disp) in enumerate(user_coords):
        print(f"\n포인트 {i+1}: 표시 좌표 ({x_disp}, {y_disp})")
        
        # 현재 구현 (문제 있는 것으로 보임)
        x_current = int(y_disp)
        y_current = int(original_h - 1 - x_disp)
        print(f"  현재 방법: ({x_current}, {y_current})")
        
        # 올바른 방법 (방법 1)
        x_correct = int(rotated_w - 1 - y_disp)
        y_correct = int(x_disp)
        print(f"  올바른 방법: ({x_correct}, {y_correct})")
        
        # 경계 검사
        x_correct = max(0, min(original_w - 1, x_correct))
        y_correct = max(0, min(original_h - 1, y_correct))
        print(f"  경계 검사 후: ({x_correct}, {y_correct})")
    
    return slice_img, rotated_img, user_coords

def visualize_transforms():
    """시각화를 통한 확인"""
    slice_img, rotated_img, user_coords = test_coordinate_transforms()
    
    # matplotlib로 시각화
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # 원본 이미지
    axes[0].imshow(slice_img, cmap='gray')
    axes[0].set_title('원본 이미지')
    axes[0].grid(True, alpha=0.3)
    
    # 회전된 이미지
    axes[1].imshow(rotated_img, cmap='gray')
    axes[1].set_title('회전된 이미지 (Gradio 표시)')
    axes[1].grid(True, alpha=0.3)
    
    # 사용자 선택 영역 표시
    x1, y1 = user_coords[0]
    x2, y2 = user_coords[1]
    
    # 회전된 이미지에 사용자 선택 박스 표시
    from matplotlib.patches import Rectangle
    rect = Rectangle((x1, y1), x2-x1, y2-y1, 
                    linewidth=2, edgecolor='green', facecolor='none', alpha=0.7)
    axes[1].add_patch(rect)
    axes[1].text(x1, y1-10, f'사용자 선택\n({x1},{y1})-({x2},{y2})', 
                color='green', fontsize=8)
    
    plt.tight_layout()
    plt.savefig('/tmp/coordinate_debug.png', dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: /tmp/coordinate_debug.png")
    
    return slice_img, rotated_img

if __name__ == "__main__":
    try:
        visualize_transforms()
        print("\n=== 디버깅 완료 ===")
        print("이제 올바른 좌표 변환을 적용해보겠습니다.")
    except Exception as e:
        print(f"디버깅 실행 오류: {e}")
        import traceback
        traceback.print_exc() 
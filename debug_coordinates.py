#!/usr/bin/env python3
"""
좌표 변환 디버깅 스크립트
"""
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

def debug_coordinate_transform():
    """좌표 변환 디버깅"""
    
    # 예제 이미지 크기 (MR 이미지와 동일)
    original_h, original_w = 480, 480
    
    # 원본 이미지 생성 (테스트용)
    original_img = np.zeros((original_h, original_w))
    
    # 테스트 포인트들 (사용자가 선택한 bounding box 좌표)
    test_points = [
        (200, 265),  # x1, y1 (좌상단)
        (240, 310),  # x2, y2 (우하단)
    ]
    
    print("=== 좌표 변환 디버깅 ===")
    print(f"원본 이미지 크기: {original_h} x {original_w}")
    
    # np.rot90(k=-1) 적용 (Gradio에서 표시되는 방식)
    rotated_img = np.rot90(original_img, k=-1)
    rotated_h, rotated_w = rotated_img.shape
    
    print(f"회전된 이미지 크기: {rotated_h} x {rotated_w}")
    
    print("\n=== 좌표 변환 테스트 ===")
    
    for i, (x_disp, y_disp) in enumerate(test_points):
        print(f"\n테스트 포인트 {i+1}: 표시 좌표 ({x_disp}, {y_disp})")
        
        # 현재 구현된 변환 (잘못된 것으로 의심)
        x_orig_current = int(y_disp)
        y_orig_current = int(original_h - 1 - x_disp)
        
        print(f"  현재 변환: ({x_orig_current}, {y_orig_current})")
        
        # 올바른 변환들을 테스트해보자
        
        # 방법 1: np.rot90(k=-1)의 정확한 역변환
        # rot90(k=-1)는 시계방향 90도 회전
        # 역변환은 반시계방향 90도 회전: rot90(k=1)
        # 원본 (i,j) -> 회전 (j, H-1-i)
        # 역변환: 회전 (x,y) -> 원본 (W-1-y, x)
        x_orig_method1 = int(rotated_w - 1 - y_disp)
        y_orig_method1 = int(x_disp)
        
        print(f"  방법 1: ({x_orig_method1}, {y_orig_method1})")
        
        # 방법 2: 다른 해석
        x_orig_method2 = int(y_disp)
        y_orig_method2 = int(rotated_h - 1 - x_disp)
        
        print(f"  방법 2: ({x_orig_method2}, {y_orig_method2})")
        
        # 방법 3: 단순 swap
        x_orig_method3 = int(y_disp)
        y_orig_method3 = int(x_disp)
        
        print(f"  방법 3: ({x_orig_method3}, {y_orig_method3})")

def visualize_rotation():
    """회전 변환 시각화"""
    
    # 작은 테스트 이미지 생성
    img = np.zeros((5, 6))  # 5x6 이미지
    
    # 특정 위치에 값 설정
    img[1, 2] = 1  # (1, 2) 위치
    img[3, 4] = 2  # (3, 4) 위치
    
    print("\n=== 회전 시각화 ===")
    print("원본 이미지:")
    print(img)
    
    # np.rot90(k=-1) 적용
    rotated = np.rot90(img, k=-1)
    print("\nnp.rot90(k=-1) 후:")
    print(rotated)
    
    # 역변환 테스트
    restored = np.rot90(rotated, k=1)
    print("\n역변환 (k=1):")
    print(restored)
    
    print(f"\n원본과 역변환 동일: {np.array_equal(img, restored)}")

if __name__ == "__main__":
    debug_coordinate_transform()
    visualize_rotation() 
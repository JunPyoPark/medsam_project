#!/usr/bin/env python3
import gradio as gr
import os

def test_upload(file):
    print(f"[DEBUG] File upload received: {file}")
    if file is None:
        return "❌ No file received"
    
    print(f"[DEBUG] File path: {file}")
    print(f"[DEBUG] File exists: {os.path.exists(file)}")
    
    if os.path.exists(file):
        file_size = os.path.getsize(file)
        print(f"[DEBUG] File size: {file_size} bytes")
        
        # 파일 확장자 확인
        if file.endswith('.nii.gz'):
            return f"✅ NIfTI file uploaded successfully!\nPath: {file}\nSize: {file_size} bytes"
        else:
            return f"⚠️ File uploaded but not .nii.gz\nPath: {file}\nSize: {file_size} bytes"
    else:
        return f"❌ File path received but file doesn't exist: {file}"

# 간단한 업로드 테스트 인터페이스
with gr.Blocks(title="File Upload Test") as demo:
    gr.Markdown("# 파일 업로드 테스트")
    
    with gr.Row():
        file_input = gr.File(
            label="파일 업로드 테스트 (.nii.gz)", 
            file_types=[".nii.gz"],
            type="filepath"
        )
    
    with gr.Row():
        output = gr.Textbox(label="결과", lines=5)
    
    file_input.change(fn=test_upload, inputs=file_input, outputs=output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, share=False, show_api=False) 
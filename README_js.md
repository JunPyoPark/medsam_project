# MedSAM JS Frontend

This is a new, React-based frontend for the MedSAM project, designed to replace the temporary Gradio viewer. It offers a more responsive and user-friendly interface for 3D medical image segmentation.

## Features

- **Interactive Slice Viewer**: Navigate through NIfTI slices using the mouse wheel.
- **Canvas-based Drawing**: Draw bounding boxes directly on the image for 2D segmentation.
- **Real-time Feedback**: View segmentation results overlaid on the image immediately.
- **3D Propagation**: Easily configure and trigger 3D propagation tasks.
- **Status Logging**: Monitor the progress of your tasks with a detailed system log.
- **Modern UI/UX**: 
    - **Glassmorphism Design**: Sleek, dark-themed interface with translucent panels.
    - **Responsive Layout**: Full-screen viewer with floating controls.
    - **Help Modal**: Built-in quick guide for new users.

## Prerequisites

- Node.js (v18 or higher)
- npm

## Getting Started

1.  **Start the Backend API**:
    Ensure the MedSAM API server is running.
    ```bash
    ./start_server.sh
    ```

2.  **Start the Frontend**:
    Run the startup script:
    ```bash
    ./scripts/start_js_frontend.sh
    ```
    Or manually:
    ```bash
    cd medsam_js_viewer
    npm install
    npm run dev
    ```

3.  **Access the App**:
    Open your browser and navigate to `http://localhost:5173`.

## Usage

1.  **Upload**: Drag and drop a `.nii.gz` file into the upload area.
2.  **Navigate**: Use the mouse wheel to scroll through slices.
3.  **Segment 2D**:
    - Draw a bounding box around the object of interest on a slice.
    - Click "Segment 2D" in the control panel.
    - The segmentation mask will appear as a red overlay.
4.  **Propagate 3D**:
    - Set the "Start Slice" and "End Slice" for propagation.
    - The "Ref Slice" is automatically set to the slice you just segmented.
    - Click "Propagate 3D".
    - Wait for the process to complete and download the result.

## Tech Stack

- **React**: UI Library
- **Vite**: Build Tool
- **Tailwind CSS**: Styling
- **nifti-reader-js**: NIfTI File Parsing
- **Axios**: API Communication

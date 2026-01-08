import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import NiftiUploader from './components/NiftiUploader';
import SliceViewer from './components/SliceViewer';
import ControlPanel from './components/ControlPanel';
import StatusLog from './components/StatusLog';
import { loadNiftiFile, getSlice, getMaskSlice } from './utils/nifti';
import { createJob, triggerSegmentation, getJobStatus, getJobResult, triggerPropagation, getJobResultBlob } from './utils/api';
import { Loader2 } from 'lucide-react';
import * as nifti from 'nifti-reader-js';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function App() {
  const [niftiData, setNiftiData] = useState(null);
  const [currentSlice, setCurrentSlice] = useState(0);
  const [jobId, setJobId] = useState(null);

  // Slice-specific state
  const [bboxes, setBboxes] = useState({}); // { sliceIndex: {x1, y1, x2, y2} }
  const [maskOverlays, setMaskOverlays] = useState({}); // { sliceIndex: ImageData }

  // 3D Volume state
  const [maskVolume, setMaskVolume] = useState(null); // Parsed NIfTI object for 3D mask

  const [logs, setLogs] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // 3D Propagation State
  const [startSlice, setStartSlice] = useState(0);
  const [endSlice, setEndSlice] = useState(0);
  const [refSlice, setRefSlice] = useState(0);
  const [resultBlobUrl, setResultBlobUrl] = useState(null);

  // Editing State
  const [editMode, setEditMode] = useState('bbox'); // 'view', 'bbox', 'brush', 'eraser'
  const [brushSize, setBrushSize] = useState(10);

  // Windowing State
  const [windowWidth, setWindowWidth] = useState(400);
  const [windowLevel, setWindowLevel] = useState(40);
  const [isAutoWindow, setIsAutoWindow] = useState(true);

  const addLog = (message) => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { time, message }]);
  };

  // Helper to get current slice artifacts
  const currentBbox = bboxes[currentSlice] || null;

  // Cache for 3D mask slices to avoid recalculation
  const maskCache = useRef({});

  // Helper to get current mask overlay
  // Priority: 3D Volume Slice > 2D Mask Overlay
  const getCurrentMask = () => {
    if (maskVolume && niftiData) {
      // Check cache first
      if (maskCache.current[currentSlice]) {
        return maskCache.current[currentSlice];
      }

      // Extract slice from 3D volume
      try {
        const maskSlice = getMaskSlice(maskVolume, currentSlice);
        // Cache it
        maskCache.current[currentSlice] = maskSlice;
        return maskSlice;
      } catch (e) {
        console.error("Error extracting mask slice:", e);
        return null;
      }
    }
    return maskOverlays[currentSlice] || null;
  };

  const handleUpload = async (file) => {
    setIsProcessing(true);
    addLog(`Uploading ${file.name}...`);
    try {
      // Load NIfTI locally for visualization
      const data = await loadNiftiFile(file);
      setNiftiData(data);

      const midSlice = Math.floor(data.header.dims[3] / 2);
      setCurrentSlice(midSlice);
      setStartSlice(0);
      setEndSlice(data.header.dims[3] - 1);
      setRefSlice(midSlice);

      // Reset state
      setBboxes({});
      setMaskOverlays({});
      setMaskVolume(null);
      maskCache.current = {};

      addLog('File loaded locally. Creating job on server...');

      // Create job on server
      const response = await createJob(file);
      if (response.job_id) {
        setJobId(response.job_id);
        addLog(`Job created: ${response.job_id} `);
      } else {
        addLog('Error: No job ID returned');
      }
    } catch (err) {
      console.error(err);
      addLog(`Error: ${err.message} `);
    } finally {
      setIsProcessing(false);
    }
  };

  const pollJobStatus = async (jid, onComplete, onError) => {
    const startTime = Date.now();
    const TIMEOUT_MS = 300000; // 5 minutes timeout

    const poll = async () => {
      try {
        // Check for client-side timeout
        if (Date.now() - startTime > TIMEOUT_MS) {
          throw new Error("Polling timed out (5 minutes limit)");
        }

        const statusData = await getJobStatus(jid);

        if (statusData.status === 'completed') {
          onComplete(statusData);
          return;
        } else if (statusData.status === 'failed') {
          console.error("Job Failed:", statusData);
          const errorMsg = statusData.error_details?.error || "Unknown error";
          if (onError) onError(errorMsg);
          addLog(`Job failed: ${errorMsg}`);
          setIsProcessing(false);
          return;
        }

        // Continue polling
        if (statusData.status === 'processing' && statusData.progress) {
          // Optional: update progress bar
        }
        setTimeout(poll, 2000);
      } catch (err) {
        console.error("Polling Error:", err);

        // Handle 503 Service Unavailable (Server Busy) specifically
        if (err.response && err.response.status === 503) {
          addLog(`Server busy (Queue pos: ${err.response.data?.detail?.queue_position || '?'}). Retrying...`);
          setTimeout(poll, 5000); // Wait longer for retry
          return;
        }

        const errorMsg = err.response?.data?.detail?.message || err.message || "Network Error";
        addLog(`Error: ${errorMsg}`);
        if (onError) onError(errorMsg);
        setIsProcessing(false);
      }
    };
    poll();
  };

  const handleBoxChange = (newBox) => {
    setBboxes(prev => ({
      ...prev,
      [currentSlice]: newBox
    }));
  };

  const handleSegment2D = async () => {
    if (!jobId || !currentBbox) return;
    setIsProcessing(true);
    addLog(`Starting 2D segmentation on slice ${currentSlice}...`);

    try {
      // Convert display coords to original coords if needed
      // Since we display 1:1 pixel mapping in canvas (mostly), 
      // we might need to check if scaling is applied.
      // For now assuming 1:1 or handled by backend if we pass what we see.
      // Our SliceViewer draws on a canvas sized to the image dimensions, 
      // so the coordinates should be correct relative to the image.

      // Ensure integer values for API
      const safeSlice = Math.round(currentSlice);

      // User confirmed original coordinates match Gradio and NIfTI orientation is correct.
      // So we send coordinates as is (just rounded).
      const safeBbox = {
        x1: Math.round(currentBbox.x1),
        y1: Math.round(currentBbox.y1),
        x2: Math.round(currentBbox.x2),
        y2: Math.round(currentBbox.y2)
      };

      addLog(`Sending BBox: ${JSON.stringify(safeBbox)} `);

      // Prepare Window Level if not auto
      let windowLevelData = null;
      if (!isAutoWindow) {
        windowLevelData = [windowWidth, windowLevel];
        addLog(`Sending Window Level: [${windowWidth}, ${windowLevel}]`);
      }

      await triggerSegmentation(jobId, safeSlice, safeBbox, windowLevelData);

      pollJobStatus(jobId, async () => {
        addLog('2D Segmentation completed. Fetching result...');
        const result = await getJobResult(jobId);
        if (result.success && result.result.mask_data) {
          // Process mask data for display
          // result.result.mask_data is base64 encoded string
          const maskBase64 = result.result.mask_data;
          const img = new Image();
          img.onload = () => {
            // Draw mask directly to canvas
            const c = document.createElement('canvas');
            c.width = img.width;
            c.height = img.height;
            const ctx = c.getContext('2d');
            ctx.drawImage(img, 0, 0);
            const imageData = ctx.getImageData(0, 0, c.width, c.height);

            // Colorize the mask (red)
            const data = imageData.data;
            for (let i = 0; i < data.length; i += 4) {
              // Assuming mask is grayscale or binary
              if (data[i] > 0) { // If pixel is not black
                data[i] = 255;     // R
                data[i + 1] = 0;     // G
                data[i + 2] = 0;     // B
                data[i + 3] = 128;   // A (semi-transparent)
              } else {
                data[i + 3] = 0; // Transparent
              }
            }

            setMaskOverlays(prev => ({
              ...prev,
              [currentSlice]: imageData
            }));

            addLog('Mask overlay updated.');
            setIsProcessing(false);
            setRefSlice(currentSlice); // Update ref slice to current
          };
          img.src = `data: image / png; base64, ${maskBase64} `;
        } else {
          addLog('Error: Invalid result data');
          setIsProcessing(false);
        }
      });
    } catch (err) {
      addLog(`Error: ${err.message} `);
      setIsProcessing(false);
    }
  };

  const handlePropagate3D = async () => {
    if (!jobId) return;
    setIsProcessing(true);
    addLog(`Starting 3D propagation(${startSlice} -> ${endSlice}, ref: ${refSlice})...`);

    try {
      // We need the mask data from the previous result to pass it back?
      // Actually the backend stores state? 
      // Looking at app.py: trigger_propagation fetches result from backend first.
      // So we just need to trigger it.

      // Wait, app.py fetches result from backend and sends it back in 'mask_data'.
      // So we need to do the same.
      // Use the local mask data (which might be edited)
      const currentMaskData = maskOverlays[refSlice];

      let maskBase64 = null;
      if (currentMaskData) {
        const canvas = document.createElement('canvas');
        canvas.width = currentMaskData.width;
        canvas.height = currentMaskData.height;
        const ctx = canvas.getContext('2d');

        // Check if data is 1-channel compressed (Uint8Array)
        if (currentMaskData.data instanceof Uint8Array && !(currentMaskData instanceof ImageData)) {
          // Reconstruct ImageData from 1-channel
          const { data, width, height } = currentMaskData;
          const rgbaData = new Uint8ClampedArray(width * height * 4);
          for (let i = 0; i < width * height; i++) {
            const val = data[i];
            if (val > 0) {
              const idx = i * 4;
              rgbaData[idx] = 255;     // R
              rgbaData[idx + 1] = 255; // G
              rgbaData[idx + 2] = 255; // B
              rgbaData[idx + 3] = 255; // A
            }
          }
          const imageData = new ImageData(rgbaData, width, height);
          ctx.putImageData(imageData, 0, 0);
        } else {
          // Legacy/Fallback: ImageData
          ctx.putImageData(currentMaskData, 0, 0);
        }

        const dataURL = canvas.toDataURL('image/png');
        maskBase64 = dataURL.split(',')[1]; // Remove prefix
      } else {
        // Fallback to backend result if local not found (shouldn't happen if segmented)
        const prevResult = await getJobResult(jobId);
        if (prevResult.success && prevResult.result.mask_data) {
          maskBase64 = prevResult.result.mask_data;
        }
      }

      if (!maskBase64) {
        throw new Error("No mask available for propagation. Please segment a slice first.");
      }

      // Prepare Window Level if not auto
      let windowLevelData = null;
      if (!isAutoWindow) {
        windowLevelData = [windowWidth, windowLevel];
        addLog(`Sending Window Level for 3D: [${windowWidth}, ${windowLevel}]`);
      }

      await triggerPropagation(jobId, startSlice, endSlice, refSlice, maskBase64, windowLevelData);

      pollJobStatus(jobId, async (status) => {
        addLog('3D Propagation completed!');

        // 1. Download result for visualization
        try {
          addLog('Downloading 3D result for visualization...');
          const blob = await getJobResultBlob(jobId);

          // Parse NIfTI
          if (nifti.isCompressed(blob)) {
            const data = nifti.decompress(blob);
            if (nifti.isNIFTI(data)) {
              const header = nifti.readHeader(data);
              const image = nifti.readImage(header, data);

              // Create object compatible with our getSlice utility
              const volumeObject = {
                header: header,
                image: image,
                // Add helper to get slice data like our loadNiftiFile does
                getSlice: (sliceIdx) => {
                  // This logic is duplicated from nifti.js, we should reuse or mock it
                  // For now, we rely on the fact that getSlice utility takes this object
                  return null; // getSlice utility handles the extraction
                }
              };
              // Actually, our getSlice utility expects {header, image}. 
              // We need to make sure the data format matches what getSlice expects.
              // loadNiftiFile returns an object with getSlice method attached.
              // Let's just attach the raw data and let getSlice utility handle it if we export it properly.
              // Wait, getSlice in nifti.js is exported.

              setMaskVolume({ header, image });
              addLog('3D Mask Volume loaded for visualization.');
            }
            // 2. Prepare for manual download
            const blobUrl = URL.createObjectURL(new Blob([blob]));
            setResultBlobUrl(blobUrl);
            addLog('3D Result ready for download.');
          }
        } catch (e) {
          addLog(`Error loading 3D result: ${e.message} `);
        }

        setIsProcessing(false);
      });

    } catch (err) {
      console.error("Propagation Error:", err);
      addLog(`Error: ${err.message || JSON.stringify(err)}`);
      setIsProcessing(false);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col relative">
      <Header />

      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* Main Viewer Area */}
        <div className="flex-1 relative bg-slate-950/50 flex items-center justify-center overflow-hidden">
          {!niftiData ? (
            <div className="w-full max-w-2xl px-6 animate-fade-in">
              <NiftiUploader onUpload={handleUpload} isLoading={isProcessing} />
            </div>
          ) : (
            <div className="w-full h-full flex flex-col animate-fade-in">
              <SliceViewer
                niftiData={niftiData}
                currentSlice={currentSlice}
                onSliceChange={(newSlice) => {
                  setCurrentSlice(newSlice);
                  // Update ref slice if we are just browsing? No, ref slice is set by segmentation.
                  // But we might want to sync them.
                  setRefSlice(newSlice);
                }}
                onBBoxDrawn={handleBoxChange}
                // If we have a 3D mask volume, we don't pass the 2D overlay.
                // The worker handles the merged visualization.
                maskOverlay={maskVolume ? null : getCurrentMask()}
                boundingBox={currentBbox}
                maskVolume={maskVolume}
                // Edit Props
                editMode={editMode}
                brushSize={brushSize}
                onMaskChange={(newMaskData) => {
                  setMaskOverlays(prev => ({
                    ...prev,
                    [currentSlice]: newMaskData
                  }));
                }}
                // Windowing Props
                windowWidth={windowWidth}
                windowLevel={windowLevel}
                isAutoWindow={isAutoWindow}
              />
            </div>
          )}

          {/* Loading Overlay */}
          {isProcessing && (
            <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
              <div className="glass-panel p-8 flex flex-col items-center gap-4">
                <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
                <p className="text-lg font-medium text-primary-200">Processing...</p>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Controls */}
        <div className="w-96 glass border-l border-white/5 flex flex-col z-20 shadow-2xl">
          <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
            <ControlPanel
              onSegment2D={handleSegment2D}
              onPropagate3D={handlePropagate3D}
              startSlice={startSlice}
              setStartSlice={setStartSlice}
              endSlice={endSlice}
              setEndSlice={setEndSlice}
              refSlice={refSlice}
              setRefSlice={setRefSlice}
              isProcessing={isProcessing}
              bbox={currentBbox}
              jobId={jobId}
              hasNifti={!!niftiData}
              resultBlobUrl={resultBlobUrl}
              editMode={editMode}
              setEditMode={setEditMode}
              brushSize={brushSize}
              setBrushSize={setBrushSize}
              // Windowing Props
              windowWidth={windowWidth}
              setWindowWidth={setWindowWidth}
              windowLevel={windowLevel}
              setWindowLevel={setWindowLevel}
              isAutoWindow={isAutoWindow}
              setIsAutoWindow={setIsAutoWindow}
            />

            <div className="pt-4 border-t border-white/10">
              <StatusLog logs={logs} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

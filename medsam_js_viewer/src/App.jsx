import React, { useState } from 'react';
import Header from './components/Header';
import NiftiUploader from './components/NiftiUploader';
import SliceViewer from './components/SliceViewer';
import ControlPanel from './components/ControlPanel';
import StatusLog from './components/StatusLog';
import { loadNiftiFile } from './utils/nifti';
import { createJob, triggerSegmentation, getJobStatus, getJobResult, triggerPropagation } from './utils/api';
import { Loader2 } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000'; // Should match api.js

function App() {
  const [niftiData, setNiftiData] = useState(null);
  const [currentSlice, setCurrentSlice] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [bbox, setBbox] = useState(null);
  const [maskOverlay, setMaskOverlay] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // 3D Propagation State
  const [startSlice, setStartSlice] = useState(0);
  const [endSlice, setEndSlice] = useState(0);
  const [refSlice, setRefSlice] = useState(0);

  const addLog = (message) => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { time, message }]);
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

      addLog('File loaded locally. Creating job on server...');

      // Create job on server
      const response = await createJob(file);
      if (response.job_id) {
        setJobId(response.job_id);
        addLog(`Job created: ${response.job_id}`);
      } else {
        addLog('Error: No job ID returned');
      }
    } catch (err) {
      console.error(err);
      addLog(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const pollJobStatus = async (jid, onComplete) => {
    const poll = async () => {
      try {
        const statusData = await getJobStatus(jid);
        if (statusData.status === 'completed') {
          onComplete(statusData);
          return;
        } else if (statusData.status === 'failed') {
          addLog(`Job failed: ${statusData.error_details}`);
          setIsProcessing(false);
          return;
        }

        // Continue polling
        if (statusData.status === 'processing' && statusData.progress) {
          // Optional: update progress bar
        }
        setTimeout(poll, 2000);
      } catch (err) {
        addLog(`Polling error: ${err.message}`);
        setIsProcessing(false);
      }
    };
    poll();
  };

  const handleSegment2D = async () => {
    if (!jobId || !bbox) return;
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
        x1: Math.round(bbox.x1),
        y1: Math.round(bbox.y1),
        x2: Math.round(bbox.x2),
        y2: Math.round(bbox.y2)
      };

      addLog(`Sending BBox: ${JSON.stringify(safeBbox)}`);

      await triggerSegmentation(jobId, safeSlice, safeBbox);

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

            setMaskOverlay(imageData);
            addLog('Mask overlay updated.');
            setIsProcessing(false);
            setRefSlice(currentSlice); // Update ref slice to current
          };
          img.src = `data:image/png;base64,${maskBase64}`;
        } else {
          addLog('Error: Invalid result data');
          setIsProcessing(false);
        }
      });
    } catch (err) {
      addLog(`Error: ${err.message}`);
      setIsProcessing(false);
    }
  };

  const handlePropagate3D = async () => {
    if (!jobId) return;
    setIsProcessing(true);
    addLog(`Starting 3D propagation (${startSlice} -> ${endSlice}, ref: ${refSlice})...`);

    try {
      // We need the mask data from the previous result to pass it back?
      // Actually the backend stores state? 
      // Looking at app.py: trigger_propagation fetches result from backend first.
      // So we just need to trigger it.

      // Wait, app.py fetches result from backend and sends it back in 'mask_data'.
      // So we need to do the same.
      const prevResult = await getJobResult(jobId);
      if (!prevResult.success || !prevResult.result.mask_data) {
        throw new Error("No 2D mask available for propagation");
      }

      await triggerPropagation(jobId, startSlice, endSlice, refSlice, prevResult.result.mask_data);

      pollJobStatus(jobId, (status) => {
        addLog('3D Propagation completed!');
        const downloadUrl = `${API_BASE}/api/v1/jobs/${jobId}/result`;
        // Create a clickable link in the logs (or we could add a button in UI)
        // For now, let's just log it and maybe set a state to show a download button
        addLog(`Download result: ${downloadUrl}`);

        // Trigger download automatically or show a button?
        // Let's create a temporary anchor to download
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `${jobId}_result.nii.gz`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        addLog('Download started automatically.');

        setIsProcessing(false);
      });

    } catch (err) {
      addLog(`Error: ${err.message}`);
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
                  setRefSlice(newSlice);
                }}
                onBoxChange={setBbox}
                maskOverlay={maskOverlay}
                boundingBox={bbox}
              />
            </div>
          )}

          {/* Loading Overlay */}
          {isProcessing && (
            <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
              <div className="glass-panel p-8 flex flex-col items-center gap-4">
                <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
                <p className="text-lg font-medium text-indigo-200">Processing...</p>
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
              bbox={bbox}
              jobId={jobId}
              hasNifti={!!niftiData}
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

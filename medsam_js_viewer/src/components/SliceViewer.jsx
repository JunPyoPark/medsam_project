
import React, { useRef, useEffect, useState, useMemo } from 'react';
import NiftiWorker from '../workers/niftiWorker?worker'; // Vite worker import

const SliceViewer = ({ niftiData, currentSlice, maskOverlay, boundingBox, onSliceChange, onBBoxDrawn, maskVolume, editMode, brushSize, onMaskChange, windowWidth, windowLevel, isAutoWindow }) => {
    const containerRef = useRef(null);
    const baseCanvasRef = useRef(null);
    const maskCanvasRef = useRef(null);
    const uiCanvasRef = useRef(null);

    const [isDrawing, setIsDrawing] = useState(false);
    const [startPos, setStartPos] = useState({ x: 0, y: 0 });
    const [tempBox, setTempBox] = useState(null);

    // Worker State
    const workerRef = useRef(null);
    const [bitmaps, setBitmaps] = useState({ base: null, mask: null });
    const [isWorkerReady, setIsWorkerReady] = useState(false);

    // 1. Initialize Worker
    useEffect(() => {
        workerRef.current = new NiftiWorker();

        workerRef.current.onmessage = (e) => {
            const { type, payload } = e.data;
            if (type === 'IMAGE_LOADED') {
                setIsWorkerReady(true);
            } else if (type === 'SLICE_READY') {
                const { sliceIndex, baseBitmap, maskBitmap } = payload;
                // Only update if it matches current slice (discard old requests)
                // Note: In a real app we might want to cache these
                setBitmaps({ base: baseBitmap, mask: maskBitmap });
            } else if (type === 'ERROR') {
                console.error("Worker Error:", payload);
            }
        };

        return () => {
            workerRef.current.terminate();
        };
    }, []);

    // 2. Send Data to Worker
    useEffect(() => {
        if (!workerRef.current || !niftiData) return;

        // We need to send the raw buffer. 
        // niftiData.image is an ArrayBuffer or TypedArray.
        // We should send the original ArrayBuffer if possible, or a copy.
        // Since niftiData is prop, we might not want to transfer it (it would empty the prop).
        // So we send a copy.
        // Wait, niftiData.image is the raw image data buffer.
        // Let's send the whole file data if we have it, or just the image.
        // Our worker expects the file data to parse header itself?
        // Let's look at niftiWorker.js: expects { data } in LOAD_IMAGE.

        // We need to pass the raw ArrayBuffer of the file.
        // But niftiData from loadNiftiFile returns { header, image, data }.
        // 'data' is the decompressed buffer or original buffer.
        if (niftiData.data) {
            workerRef.current.postMessage({
                type: 'LOAD_IMAGE',
                payload: { data: niftiData.data }
            });
        }
    }, [niftiData]);

    // 3. Send Mask Volume to Worker
    useEffect(() => {
        if (!workerRef.current || !maskVolume) return;

        // Sanitize header to remove functions (DataCloneError fix)
        const safeHeader = JSON.parse(JSON.stringify(maskVolume.header));

        workerRef.current.postMessage({
            type: 'LOAD_MASK',
            payload: { header: safeHeader, image: maskVolume.image }
        });
    }, [maskVolume]);


    // 4. Request Slice
    useEffect(() => {
        if (!workerRef.current || !isWorkerReady) return;

        workerRef.current.postMessage({
            type: 'GET_SLICE',
            payload: {
                sliceIndex: currentSlice,
                windowWidth,
                windowLevel,
                isAuto: isAutoWindow
            }
        });
    }, [currentSlice, isWorkerReady, maskVolume, windowWidth, windowLevel, isAutoWindow]); // Re-request if mask volume changes


    // 5. Render Base Layer
    useEffect(() => {
        const canvas = baseCanvasRef.current;
        if (!canvas || !bitmaps.base) return;

        const ctx = canvas.getContext('2d', { alpha: false });

        if (canvas.width !== bitmaps.base.width || canvas.height !== bitmaps.base.height) {
            canvas.width = bitmaps.base.width;
            canvas.height = bitmaps.base.height;
        }

        ctx.drawImage(bitmaps.base, 0, 0);
    }, [bitmaps.base]);

    const skipNextMaskUpdate = useRef(false);

    // 6. Render Mask Layer (2D Overlay Only)
    useEffect(() => {
        const canvas = maskCanvasRef.current;
        if (!canvas) return;

        // Skip redraw if the update was triggered by our own drawing
        if (skipNextMaskUpdate.current) {
            skipNextMaskUpdate.current = false;
            return;
        }

        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Since App.jsx now passes null for maskOverlay if maskVolume exists,
        // we can simply check for maskOverlay here.
        if (maskOverlay) {
            createImageBitmap(maskOverlay).then(bmp => {
                if (canvas.width !== bmp.width || canvas.height !== bmp.height) {
                    canvas.width = bmp.width;
                    canvas.height = bmp.height;
                }
                ctx.drawImage(bmp, 0, 0);
            });
        } else if (bitmaps.mask) {
            // Render 3D Volume Mask from Worker
            if (canvas.width !== bitmaps.mask.width || canvas.height !== bitmaps.mask.height) {
                canvas.width = bitmaps.mask.width;
                canvas.height = bitmaps.mask.height;
            }
            ctx.drawImage(bitmaps.mask, 0, 0);
        }
    }, [maskOverlay, bitmaps.mask]);

    // 7. Render UI Layer
    useEffect(() => {
        const canvas = uiCanvasRef.current;
        if (!canvas) return;

        // Sync dimensions with base canvas if possible, or container
        // For simplicity, match base slice dimensions if available
        if (bitmaps.base) {
            if (canvas.width !== bitmaps.base.width || canvas.height !== bitmaps.base.height) {
                canvas.width = bitmaps.base.width;
                canvas.height = bitmaps.base.height;
            }
        }

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const boxToDraw = tempBox || boundingBox;
        if (boxToDraw) {
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            const { x1, y1, x2, y2 } = boxToDraw;
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

            // Draw handles
            ctx.fillStyle = '#00ff00';
            const handleSize = 4;
            ctx.fillRect(x1 - handleSize / 2, y1 - handleSize / 2, handleSize, handleSize);
            ctx.fillRect(x2 - handleSize / 2, y2 - handleSize / 2, handleSize, handleSize);
            ctx.fillRect(x1 - handleSize / 2, y2 - handleSize / 2, handleSize, handleSize);
            ctx.fillRect(x2 - handleSize / 2, y1 - handleSize / 2, handleSize, handleSize);
        }
    }, [tempBox, boundingBox, bitmaps.base]); // Re-render UI when box changes or slice dims change


    // Event Handling
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const onWheel = (e) => {
            e.preventDefault();
            if (!niftiData) return;

            const maxSlice = niftiData.header.dims[3] - 1;
            const delta = e.deltaY > 0 ? 1 : -1;
            const newSlice = Math.max(0, Math.min(maxSlice, currentSlice + delta));

            if (newSlice !== currentSlice) {
                onSliceChange(newSlice);
            }
        };

        container.addEventListener('wheel', onWheel, { passive: false });

        return () => {
            container.removeEventListener('wheel', onWheel);
        };
    }, [niftiData, currentSlice, onSliceChange]);

    const getCanvasCoords = (e) => {
        const canvas = uiCanvasRef.current;
        // Use nativeEvent.offsetX/Y for more accurate relative coordinates
        // This avoids issues with getBoundingClientRect including borders/padding in ways that might offset
        const x = e.nativeEvent.offsetX;
        const y = e.nativeEvent.offsetY;

        // Scale to internal canvas resolution
        // clientWidth/Height gives the inner dimension (padding box), which matches where we draw
        const scaleX = canvas.width / canvas.clientWidth;
        const scaleY = canvas.height / canvas.clientHeight;

        return {
            x: x * scaleX,
            y: y * scaleY
        };
    };

    const handleMouseDown = (e) => {
        const coords = getCanvasCoords(e);
        setStartPos(coords);
        setIsDrawing(true);

        if (editMode === 'bbox') {
            setTempBox(null);
        } else if (editMode === 'brush' || editMode === 'eraser') {
            drawOnMask(coords);
        }
    };

    const cursorRef = useRef(null);
    const [canvasScale, setCanvasScale] = useState(1); // Keep this state but update less frequently? 
    // Actually, let's just calculate scale on the fly or use a ref if we want to avoid re-renders for scale updates.
    // But scale only changes on resize.

    // Better: Update scale in a useEffect on mount/resize.
    useEffect(() => {
        const updateScale = () => {
            const canvas = uiCanvasRef.current;
            if (canvas) {
                const rect = canvas.getBoundingClientRect();
                setCanvasScale(rect.width / canvas.width);
            }
        };

        window.addEventListener('resize', updateScale);
        updateScale(); // Initial

        return () => window.removeEventListener('resize', updateScale);
    }, [bitmaps.base]); // Update when base image changes (dims change)

    const handleMouseMove = (e) => {
        const coords = getCanvasCoords(e);

        // Direct DOM manipulation for performance
        if (cursorRef.current && uiCanvasRef.current) {
            // Use offsetX/Y directly for visual cursor position
            const x = e.nativeEvent.offsetX;
            const y = e.nativeEvent.offsetY;

            cursorRef.current.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
            cursorRef.current.style.display = 'block';
        }

        if (editMode === 'bbox') {
            if (!isDrawing) return;
            setTempBox({
                x1: Math.min(startPos.x, coords.x),
                y1: Math.min(startPos.y, coords.y),
                x2: Math.max(startPos.x, coords.x),
                y2: Math.max(startPos.y, coords.y)
            });
        } else if (editMode === 'brush' || editMode === 'eraser') {
            if (isDrawing) {
                drawOnMask(coords);
            }
        }
    };

    const handleMouseUp = (e) => {
        if (!isDrawing) return;
        setIsDrawing(false);

        if (editMode === 'bbox') {
            if (tempBox) {
                if (Math.abs(tempBox.x2 - tempBox.x1) > 5 && Math.abs(tempBox.y2 - tempBox.y1) > 5) {
                    onBBoxDrawn(tempBox);
                }
            }
            setTempBox(null);
        } else if (editMode === 'brush' || editMode === 'eraser') {
            // Save the mask change
            const canvas = maskCanvasRef.current;
            if (canvas && onMaskChange) {
                // Set flag to skip the next prop update since we already have the data on canvas
                skipNextMaskUpdate.current = true;

                const ctx = canvas.getContext('2d', { willReadFrequently: true });
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

                // Compress to 1-channel (Uint8Array)
                const len = canvas.width * canvas.height;
                const compressedData = new Uint8Array(len);
                const rawData = imageData.data;

                for (let i = 0; i < len; i++) {
                    // Check Red channel (or Alpha)
                    compressedData[i] = rawData[i * 4] > 0 ? 1 : 0;
                }

                onMaskChange({
                    data: compressedData,
                    width: canvas.width,
                    height: canvas.height
                });
            }
        }
    };

    const handleMouseLeave = () => {
        handleMouseUp();
        if (cursorRef.current) {
            cursorRef.current.style.display = 'none';
        }
    };

    const drawOnMask = (coords) => {
        const canvas = maskCanvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });

        ctx.beginPath();
        ctx.arc(coords.x, coords.y, brushSize / 2, 0, Math.PI * 2);

        if (editMode === 'eraser') {
            ctx.globalCompositeOperation = 'destination-out';
            ctx.fill();
            ctx.globalCompositeOperation = 'source-over';
        } else {
            // Use solid color for data robustness
            // Visual transparency is handled by canvas opacity
            ctx.fillStyle = 'rgba(255, 0, 0, 1.0)';
            ctx.fill();
        }
    };

    return (
        <div
            ref={containerRef}
            className="w-full h-full flex items-center justify-center bg-slate-950/50 relative overflow-hidden group"
        >
            <div className="relative shadow-2xl shadow-black/50 rounded-lg overflow-hidden border border-white/10 transition-transform duration-300 group-hover:scale-[1.01]">
                {/* Layer 1: Base Image */}
                <canvas
                    ref={baseCanvasRef}
                    className="block max-h-[85vh] max-w-full object-contain"
                />

                {/* Layer 2: Mask Overlay */}
                <canvas
                    ref={maskCanvasRef}
                    className="absolute inset-0 w-full h-full pointer-events-none transition-opacity duration-200"
                    style={{ opacity: 0.5 }} // Visual transparency only, data is solid
                />

                {/* Layer 3: UI / Interaction */}
                <canvas
                    ref={uiCanvasRef}
                    className={`absolute inset-0 w-full h-full ${(editMode === 'brush' || editMode === 'eraser') ? 'cursor-none' : 'cursor-crosshair'
                        }`}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseLeave}
                />

                {/* Brush Cursor Overlay - Optimized */}
                {(editMode === 'brush' || editMode === 'eraser') && (
                    <div
                        ref={cursorRef}
                        className="pointer-events-none absolute border border-white bg-white/20 rounded-full shadow-sm z-50"
                        style={{
                            left: 0,
                            top: 0,
                            width: brushSize * canvasScale,
                            height: brushSize * canvasScale,
                            display: 'none', // Initially hidden, shown by JS
                            willChange: 'transform' // Hint for GPU acceleration
                        }}
                    />
                )}

                {/* Slice Indicator Badge */}
                <div className="absolute top-4 left-4 glass px-3 py-1.5 rounded-full text-xs font-medium text-white flex items-center gap-2 pointer-events-none">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    Slice: {currentSlice} / {niftiData?.header?.dims[3] - 1}
                </div>

                {/* Helper Text */}
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 glass px-4 py-2 rounded-full text-xs text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                    Scroll to navigate • Drag to select
                </div>
            </div>
        </div>
    );
};

export default SliceViewer;

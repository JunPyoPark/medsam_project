import React, { useRef, useEffect, useState, useMemo } from 'react';
import { getSlice } from '../utils/nifti';

const SliceViewer = ({ niftiData, currentSlice, maskOverlay, boundingBox, onSliceChange, onBBoxDrawn }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [startPos, setStartPos] = useState({ x: 0, y: 0 });
    const [tempBox, setTempBox] = useState(null);

    const offscreenCanvasRef = useRef(null);

    // Memoize slice generation to avoid re-calculation on every render
    const sliceData = useMemo(() => {
        if (!niftiData) return null;
        try {
            return getSlice(niftiData, currentSlice);
        } catch (e) {
            console.error("SliceViewer: Error generating slice", e);
            return null;
        }
    }, [niftiData, currentSlice]);

    useEffect(() => {
        if (!sliceData || !canvasRef.current) return;

        let animationFrameId;

        const render = () => {
            const canvas = canvasRef.current;
            const ctx = canvas.getContext('2d', { alpha: false });

            // Resize canvas if needed
            if (canvas.width !== sliceData.width || canvas.height !== sliceData.height) {
                canvas.width = sliceData.width;
                canvas.height = sliceData.height;
            }

            // Draw slice
            ctx.putImageData(sliceData, 0, 0);

            // Draw Mask Overlay if exists
            if (maskOverlay) {
                // Initialize offscreen canvas if needed
                if (!offscreenCanvasRef.current) {
                    offscreenCanvasRef.current = document.createElement('canvas');
                }
                const offCanvas = offscreenCanvasRef.current;

                // Resize offscreen canvas if needed
                if (offCanvas.width !== maskOverlay.width || offCanvas.height !== maskOverlay.height) {
                    offCanvas.width = maskOverlay.width;
                    offCanvas.height = maskOverlay.height;
                }

                const offCtx = offCanvas.getContext('2d');
                offCtx.clearRect(0, 0, offCanvas.width, offCanvas.height);
                offCtx.putImageData(maskOverlay, 0, 0);

                ctx.drawImage(offCanvas, 0, 0);
            }

            // Draw Bounding Box (Temp or Final)
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
        };

        // Use requestAnimationFrame to throttle
        animationFrameId = requestAnimationFrame(render);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [sliceData, tempBox, boundingBox, maskOverlay]);

    // Handle wheel event manually to support non-passive listener
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
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    };

    const handleMouseDown = (e) => {
        const coords = getCanvasCoords(e);
        setStartPos(coords);
        setIsDrawing(true);
        setTempBox(null);
    };

    const handleMouseMove = (e) => {
        if (!isDrawing) return;
        const coords = getCanvasCoords(e);
        setTempBox({
            x1: Math.min(startPos.x, coords.x),
            y1: Math.min(startPos.y, coords.y),
            x2: Math.max(startPos.x, coords.x),
            y2: Math.max(startPos.y, coords.y)
        });
    };

    const handleMouseUp = (e) => {
        if (!isDrawing) return;
        setIsDrawing(false);
        if (tempBox) {
            // Only set if box has size
            if (Math.abs(tempBox.x2 - tempBox.x1) > 5 && Math.abs(tempBox.y2 - tempBox.y1) > 5) {
                onBBoxDrawn(tempBox);
            }
        }
        setTempBox(null);
    };

    return (
        <div
            ref={containerRef}
            className="w-full h-full flex items-center justify-center bg-slate-950/50 relative overflow-hidden group"
        >
            <div className="relative shadow-2xl shadow-black/50 rounded-lg overflow-hidden border border-white/10 transition-transform duration-300 group-hover:scale-[1.01]">
                <canvas
                    ref={canvasRef}
                    className="cursor-crosshair block max-h-[85vh] max-w-full object-contain"
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                />

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

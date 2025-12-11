import React, { useRef, useEffect, useState } from 'react';
import { getSlice } from '../utils/nifti';

const SliceViewer = ({ niftiData, currentSlice, onSliceChange, onBoxChange, maskOverlay, boundingBox }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [startPos, setStartPos] = useState({ x: 0, y: 0 });
    const [tempBox, setTempBox] = useState(null);

    useEffect(() => {
        if (!niftiData || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');

        // Get slice data
        const slice = getSlice(niftiData, currentSlice);

        // Resize canvas to match image dims
        if (canvas.width !== slice.width || canvas.height !== slice.height) {
            canvas.width = slice.width;
            canvas.height = slice.height;
        }

        // Draw slice
        ctx.putImageData(slice, 0, 0);

        // Draw Mask Overlay if exists
        if (maskOverlay) {
            // Create temp canvas to draw mask with opacity
            const tempC = document.createElement('canvas');
            tempC.width = maskOverlay.width;
            tempC.height = maskOverlay.height;
            const tempCtx = tempC.getContext('2d');
            tempCtx.putImageData(maskOverlay, 0, 0);

            ctx.globalAlpha = 0.6;
            ctx.drawImage(tempC, 0, 0);
            ctx.globalAlpha = 1.0;
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

    }, [niftiData, currentSlice, tempBox, boundingBox, maskOverlay]);

    const handleWheel = (e) => {
        e.preventDefault();
        if (!niftiData) return;

        const maxSlice = niftiData.header.dims[3] - 1;
        const delta = e.deltaY > 0 ? 1 : -1;
        const newSlice = Math.max(0, Math.min(maxSlice, currentSlice + delta));

        if (newSlice !== currentSlice) {
            onSliceChange(newSlice);
        }
    };

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
                onBoxChange(tempBox);
            }
        }
        setTempBox(null);
    };

    return (
        <div
            ref={containerRef}
            className="w-full h-full flex items-center justify-center bg-slate-950/50 relative overflow-hidden group"
            onWheel={handleWheel}
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

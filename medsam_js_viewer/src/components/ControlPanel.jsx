import React from 'react';
import { Play, Layers, BoxSelect, Download, Activity, Brush, Eraser, MousePointer2 } from 'lucide-react';

const ControlPanel = ({
    onSegment2D,
    onPropagate3D,
    startSlice,
    setStartSlice,
    endSlice,
    setEndSlice,
    refSlice,
    setRefSlice,
    isProcessing,
    bbox,
    jobId,
    hasNifti,
    resultBlobUrl,
    editMode,
    setEditMode,
    brushSize,
    setBrushSize,
    windowWidth,
    setWindowWidth,
    windowLevel,
    setWindowLevel,
    isAutoWindow,
    setIsAutoWindow
}) => {
    if (!hasNifti) return null;

    return (
        <div className="space-y-6 animate-slide-up">
            {/* 2D Segmentation Card */}
            <div className="glass-panel p-5 space-y-4">
                <div className="flex items-center gap-2 text-primary-300 mb-2">
                    <BoxSelect className="w-5 h-5" />
                    <h3 className="font-semibold">2D Segmentation</h3>
                </div>

                {/* Tool Selection */}
                <div className="grid grid-cols-4 gap-2 bg-slate-950/30 p-1 rounded-lg border border-white/5">
                    {[
                        { id: 'view', icon: MousePointer2, label: 'View' },
                        { id: 'bbox', icon: BoxSelect, label: 'Box' },
                        { id: 'brush', icon: Brush, label: 'Brush' },
                        { id: 'eraser', icon: Eraser, label: 'Erase' }
                    ].map(tool => (
                        <button
                            key={tool.id}
                            onClick={() => setEditMode(tool.id)}
                            className={`flex flex-col items-center justify-center py-2 rounded-md transition-all duration-200 ${editMode === tool.id
                                ? 'bg-primary-500/20 text-primary-300 shadow-lg shadow-primary-500/10 border border-primary-500/30'
                                : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                                }`}
                            title={tool.label}
                        >
                            <tool.icon className="w-4 h-4 mb-1" />
                            <span className="text-[10px] font-medium">{tool.label}</span>
                        </button>
                    ))}
                </div>

                {/* Brush Size Slider */}
                {(editMode === 'brush' || editMode === 'eraser') && (
                    <div className="space-y-2 animate-fade-in">
                        <div className="flex justify-between text-xs text-slate-400">
                            <span>Size</span>
                            <span>{brushSize}px</span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="50"
                            value={brushSize}
                            onChange={(e) => setBrushSize(parseInt(e.target.value))}
                            className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                        />
                    </div>
                )}

                <div className="text-sm text-slate-400 bg-slate-950/30 p-3 rounded-lg border border-white/5">
                    <p className="flex justify-between">
                        <span>Bounding Box:</span>
                        <span className={bbox ? "text-emerald-400" : "text-slate-500"}>
                            {bbox ? "Selected" : "Draw on image"}
                        </span>
                    </p>
                </div>

                <button
                    onClick={onSegment2D}
                    disabled={!bbox || isProcessing}
                    className={`w-full btn-primary flex items-center justify-center gap-2 ${(!bbox || isProcessing) && 'opacity-50 cursor-not-allowed grayscale'}`}
                >
                    <Play className="w-4 h-4 fill-current" />
                    Segment Current Slice
                </button>
            </div>

            {/* Windowing Card */}
            <div className="glass-panel p-5 space-y-4">
                <div className="flex items-center justify-between text-primary-300 mb-2">
                    <div className="flex items-center gap-2">
                        <Activity className="w-5 h-5" />
                        <h3 className="font-semibold">Windowing</h3>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">Auto</span>
                        <button
                            onClick={() => setIsAutoWindow(!isAutoWindow)}
                            className={`w-10 h-5 rounded-full relative transition-colors duration-200 ${isAutoWindow ? 'bg-primary-500' : 'bg-slate-700'}`}
                        >
                            <div className={`absolute top-1 left-1 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${isAutoWindow ? 'translate-x-5' : 'translate-x-0'}`} />
                        </button>
                    </div>
                </div>

                {!isAutoWindow && (
                    <div className="space-y-4 animate-fade-in">
                        {/* Sliders */}
                        <div className="space-y-3">
                            <div className="space-y-1">
                                <div className="flex justify-between text-xs text-slate-400">
                                    <span>Width (Contrast)</span>
                                    <span>{windowWidth}</span>
                                </div>
                                <input
                                    type="range"
                                    min="1"
                                    max="4000"
                                    value={windowWidth}
                                    onChange={(e) => setWindowWidth(parseInt(e.target.value))}
                                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                                />
                            </div>
                            <div className="space-y-1">
                                <div className="flex justify-between text-xs text-slate-400">
                                    <span>Level (Brightness)</span>
                                    <span>{windowLevel}</span>
                                </div>
                                <input
                                    type="range"
                                    min="-1000"
                                    max="1000"
                                    value={windowLevel}
                                    onChange={(e) => setWindowLevel(parseInt(e.target.value))}
                                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                                />
                            </div>
                        </div>

                        {/* Presets */}
                        <div className="grid grid-cols-2 gap-2">
                            {[
                                { label: 'Abdomen', w: 400, l: 40 },
                                { label: 'Lung', w: 1500, l: -600 },
                                { label: 'Bone', w: 1800, l: 400 },
                                { label: 'Brain', w: 80, l: 40 }
                            ].map(preset => (
                                <button
                                    key={preset.label}
                                    onClick={() => {
                                        setWindowWidth(preset.w);
                                        setWindowLevel(preset.l);
                                    }}
                                    className="px-2 py-1.5 text-xs font-medium text-slate-400 bg-slate-950/30 border border-white/5 rounded hover:bg-white/5 hover:text-white transition-colors"
                                >
                                    {preset.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* 3D Propagation Card */}
            <div className="glass-panel p-5 space-y-4">
                <div className="flex items-center gap-2 text-primary-300 mb-2">
                    <Layers className="w-5 h-5" />
                    <h3 className="font-semibold">3D Propagation</h3>
                </div>

                <div className="space-y-3">
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-400 ml-1">Reference Slice</label>
                        <input
                            type="number"
                            value={refSlice}
                            onChange={(e) => setRefSlice(parseInt(e.target.value) || 0)}
                            className="w-full glass-input"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-slate-400 ml-1">Start Slice</label>
                            <input
                                type="number"
                                value={startSlice}
                                onChange={(e) => setStartSlice(parseInt(e.target.value) || 0)}
                                className="w-full glass-input"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-slate-400 ml-1">End Slice</label>
                            <input
                                type="number"
                                value={endSlice}
                                onChange={(e) => setEndSlice(parseInt(e.target.value) || 0)}
                                className="w-full glass-input"
                            />
                        </div>
                    </div>
                </div>

                <button
                    onClick={onPropagate3D}
                    disabled={!jobId || isProcessing}
                    className={`w-full btn-primary bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 flex items-center justify-center gap-2 ${(!jobId || isProcessing) && 'opacity-50 cursor-not-allowed grayscale'}`}
                >
                    <Activity className="w-4 h-4" />
                    Propagate 3D
                </button>

                {resultBlobUrl && (
                    <a
                        href={resultBlobUrl}
                        download={`${jobId}_result.nii.gz`}
                        className="w-full btn-secondary flex items-center justify-center gap-2 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                    >
                        <Download className="w-4 h-4" />
                        Download Result
                    </a>
                )}
            </div>
        </div>
    );
};

export default ControlPanel;

import React from 'react';
import { Play, Layers, BoxSelect, Download, Activity } from 'lucide-react';

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
    resultBlobUrl
}) => {
    if (!hasNifti) return null;

    return (
        <div className="space-y-6 animate-slide-up">
            {/* 2D Segmentation Card */}
            <div className="glass-panel p-5 space-y-4">
                <div className="flex items-center gap-2 text-indigo-300 mb-2">
                    <BoxSelect className="w-5 h-5" />
                    <h3 className="font-semibold">2D Segmentation</h3>
                </div>

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

            {/* 3D Propagation Card */}
            <div className="glass-panel p-5 space-y-4">
                <div className="flex items-center gap-2 text-violet-300 mb-2">
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
                    className={`w-full btn-primary bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 flex items-center justify-center gap-2 ${(!jobId || isProcessing) && 'opacity-50 cursor-not-allowed grayscale'}`}
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

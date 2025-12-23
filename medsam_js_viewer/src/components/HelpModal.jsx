import React from 'react';
import { X, MousePointer2, BoxSelect, Play, Layers } from 'lucide-react';

const HelpModal = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm animate-fade-in">
            <div className="w-full max-w-md glass-panel p-6 relative animate-slide-up">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>

                <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                    <span className="w-2 h-6 bg-primary-500 rounded-full"></span>
                    Quick Guide
                </h2>

                <div className="space-y-4">
                    <div className="flex gap-4 items-start p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="p-2 bg-primary-500/20 rounded-lg shrink-0">
                            <MousePointer2 className="w-5 h-5 text-primary-400" />
                        </div>
                        <div>
                            <h3 className="font-medium text-slate-200">1. Navigation</h3>
                            <p className="text-sm text-slate-400 mt-1">
                                Upload a NIfTI file. Use your mouse wheel to scroll through slices.
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-4 items-start p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="p-2 bg-blue-500/20 rounded-lg shrink-0">
                            <BoxSelect className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                            <h3 className="font-medium text-slate-200">2. Segmentation</h3>
                            <p className="text-sm text-slate-400 mt-1">
                                Draw a bounding box around the target area on any slice.
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-4 items-start p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="p-2 bg-emerald-500/20 rounded-lg shrink-0">
                            <Play className="w-5 h-5 text-emerald-400" />
                        </div>
                        <div>
                            <h3 className="font-medium text-slate-200">3. Generate Mask</h3>
                            <p className="text-sm text-slate-400 mt-1">
                                Click "Segment 2D" to generate an initial mask for the current slice.
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-4 items-start p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="p-2 bg-pink-500/20 rounded-lg shrink-0">
                            <MousePointer2 className="w-5 h-5 text-pink-400" />
                        </div>
                        <div>
                            <h3 className="font-medium text-slate-200">4. Edit Mask</h3>
                            <p className="text-sm text-slate-400 mt-1">
                                Use the Brush and Eraser tools to refine the generated mask before propagation.
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-4 items-start p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="p-2 bg-primary-500/20 rounded-lg shrink-0">
                            <Layers className="w-5 h-5 text-primary-400" />
                        </div>
                        <div>
                            <h3 className="font-medium text-slate-200">5. 3D Propagation</h3>
                            <p className="text-sm text-slate-400 mt-1">
                                Set the start/end slices and click "Propagate 3D" to process the full volume.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-6 pt-4 border-t border-white/10 text-center">
                    <button
                        onClick={onClose}
                        className="btn-primary w-full"
                    >
                        Got it
                    </button>
                </div>
            </div>
        </div>
    );
};

export default HelpModal;

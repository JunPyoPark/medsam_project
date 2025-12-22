import React, { useCallback } from 'react';
import { UploadCloud, FileUp } from 'lucide-react';

const NiftiUploader = ({ onUpload, isLoading }) => {
    const handleDrop = useCallback((e) => {
        e.preventDefault();
        if (isLoading) return;

        const file = e.dataTransfer.files[0];
        if (file && (file.name.endsWith('.nii') || file.name.endsWith('.nii.gz'))) {
            onUpload(file);
        }
    }, [onUpload, isLoading]);

    const handleFileChange = (e) => {
        if (isLoading) return;
        const file = e.target.files[0];
        if (file) {
            onUpload(file);
        }
    };

    return (
        <div
            className={`
        w-full h-96 glass-panel border-2 border-dashed border-white/10 
        flex flex-col items-center justify-center gap-6
        transition-all duration-300 group
        ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary-500/50 hover:bg-slate-900/80 cursor-pointer'}
      `}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !isLoading && document.getElementById('file-upload').click()}
        >
            <div className="relative">
                <div className="absolute inset-0 bg-primary-500/20 blur-xl rounded-full animate-pulse"></div>
                <div className="relative p-6 bg-slate-900/50 rounded-full border border-white/10 group-hover:scale-110 transition-transform duration-300">
                    <UploadCloud className="w-12 h-12 text-primary-400" />
                </div>
            </div>

            <div className="text-center space-y-2">
                <h3 className="text-xl font-semibold text-slate-200">Upload NIfTI File</h3>
                <p className="text-slate-400 text-sm max-w-xs mx-auto">
                    Drag and drop your .nii or .nii.gz file here, or click to browse
                </p>
            </div>

            <input
                id="file-upload"
                type="file"
                accept=".nii,.nii.gz"
                className="hidden"
                onChange={handleFileChange}
                disabled={isLoading}
            />

            <button className="btn-secondary flex items-center gap-2 group-hover:border-primary-500/30 group-hover:text-primary-300">
                <FileUp className="w-4 h-4" />
                <span>Select File</span>
            </button>
        </div>
    );
};

export default NiftiUploader;

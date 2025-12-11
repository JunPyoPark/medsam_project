import React, { useState } from 'react';
import { Activity, HelpCircle } from 'lucide-react';
import HelpModal from './HelpModal';

const Header = () => {
    const [isHelpOpen, setIsHelpOpen] = useState(false);

    return (
        <>
            <header className="w-full h-16 glass border-b border-white/5 flex items-center justify-between px-6 z-30 relative">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-500/20 rounded-lg border border-indigo-500/30">
                        <Activity className="w-6 h-6 text-indigo-400" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-violet-400">
                            MedSAM2 Viewer
                        </h1>
                        <p className="text-xs text-slate-400">Interactive 3D Medical Segmentation</p>
                    </div>
                </div>

                <button
                    className="p-2 hover:bg-white/5 rounded-full transition-colors text-slate-400 hover:text-indigo-400"
                    title="Help"
                    onClick={() => setIsHelpOpen(true)}
                >
                    <HelpCircle className="w-5 h-5" />
                </button>
            </header>

            <HelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
        </>
    );
};

export default Header;

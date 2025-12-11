import React, { useEffect, useRef } from 'react';
import { Terminal } from 'lucide-react';

const StatusLog = ({ logs }) => {
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className="glass-panel p-4 h-48 flex flex-col">
            <div className="flex items-center gap-2 text-slate-400 mb-3 text-xs uppercase tracking-wider font-semibold">
                <Terminal className="w-3 h-3" />
                System Logs
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 font-mono text-xs">
                {logs.length === 0 && (
                    <p className="text-slate-600 italic">Ready...</p>
                )}
                {logs.map((log, i) => (
                    <div key={i} className="flex gap-2 animate-fade-in">
                        <span className="text-slate-500 shrink-0">[{log.time}]</span>
                        <span className="text-slate-300 break-all">{log.message}</span>
                    </div>
                ))}
                <div ref={endRef} />
            </div>
        </div>
    );
};

export default StatusLog;

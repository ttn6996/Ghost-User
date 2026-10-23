import React from "react";
import { ConsoleLog } from "@/lib/types";
import { Terminal, AlertCircle, AlertTriangle } from "lucide-react";

interface ConsoleLogsViewerProps {
  consoleLogs?: ConsoleLog[];
  pageErrors?: string[];
}

export const ConsoleLogsViewer: React.FC<ConsoleLogsViewerProps> = ({
  consoleLogs = [],
  pageErrors = [],
}) => {
  const hasPageErrors = pageErrors.length > 0;
  const hasConsoleLogs = consoleLogs.length > 0;

  if (!hasPageErrors && !hasConsoleLogs) {
    return (
      <div className="p-6 text-center border border-zinc-800 rounded-lg text-xs font-mono text-zinc-400 bg-[#0e0e11]">
        Clean execution: No browser console warnings, errors, or page crashes detected.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {hasPageErrors && (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-rose-400 font-mono uppercase tracking-wider">
            <AlertCircle className="h-4 w-4" />
            <span>Unhandled Browser Page Errors ({pageErrors.length})</span>
          </div>
          <div className="space-y-1.5 font-mono text-xs text-rose-300">
            {pageErrors.map((err, idx) => (
              <div key={idx} className="p-2.5 rounded bg-rose-950/40 border border-rose-900/40 whitespace-pre-wrap">
                {err}
              </div>
            ))}
          </div>
        </div>
      )}

      {hasConsoleLogs && (
        <div className="rounded-xl border border-zinc-800 bg-[#0c0c0e] overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-zinc-900/60 border-b border-zinc-800 text-xs font-mono text-zinc-400">
            <Terminal className="h-3.5 w-3.5 text-purple-400" />
            <span>Browser Console Logs ({consoleLogs.length})</span>
          </div>
          <div className="p-3 space-y-1.5 max-h-72 overflow-y-auto font-mono text-[11px]">
            {consoleLogs.map((log, idx) => (
              <div
                key={idx}
                className={`p-2 rounded flex items-start gap-2 ${
                  log.type === "error"
                    ? "bg-rose-950/30 text-rose-300 border border-rose-900/30"
                    : "bg-amber-950/20 text-amber-300 border border-amber-900/30"
                }`}
              >
                {log.type === "error" ? (
                  <AlertCircle className="h-3.5 w-3.5 text-rose-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 overflow-x-auto whitespace-pre-wrap">
                  <span className="font-semibold uppercase text-[10px] mr-2">[{log.type}]</span>
                  {log.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

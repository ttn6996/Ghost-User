import React, { useState } from "react";
import { TestStepResult } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import { Camera, Clock, AlertTriangle, Maximize2, X } from "lucide-react";

interface StepTimelineProps {
  steps: TestStepResult[];
}

export const StepTimeline: React.FC<StepTimelineProps> = ({ steps }) => {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  if (!steps || steps.length === 0) {
    return (
      <div className="p-8 text-center border border-zinc-800 rounded-lg text-sm text-zinc-400">
        No step results recorded yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Lightbox Modal */}
      {selectedImage && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm"
          onClick={() => setSelectedImage(null)}
        >
          <div className="relative max-w-5xl max-h-[90vh] bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
            <button
              onClick={() => setSelectedImage(null)}
              className="absolute top-3 right-3 z-10 p-1.5 rounded-lg bg-black/60 text-white hover:bg-black/90 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
            <img 
              src={selectedImage} 
              alt="Test execution artifact" 
              className="max-h-[85vh] object-contain w-auto mx-auto" 
            />
          </div>
        </div>
      )}

      {/* Ordered Timeline */}
      <div className="relative border-l border-zinc-800 ml-4 space-y-6">
        {steps.map((step) => {
          const isError = step.status === "failed" || step.status === "error";
          const screenshotUrl = step.screenshot_path ? api.getArtifactUrl(step.screenshot_path) : null;

          return (
            <div key={step.id || step.step_index} className="relative pl-6">
              {/* Dot indicator */}
              <div
                className={`absolute -left-2 top-1.5 h-4 w-4 rounded-full border-2 border-[#09090b] ${
                  step.status === "passed"
                    ? "bg-emerald-500"
                    : isError
                    ? "bg-rose-500"
                    : "bg-zinc-600"
                }`}
              />

              <div
                className={`rounded-xl border p-4 transition-all ${
                  isError
                    ? "border-rose-900/60 bg-rose-950/20"
                    : "border-zinc-800/80 bg-[#111114]"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-zinc-400">
                      #{step.step_index + 1}
                    </span>
                    <span className="font-mono text-sm font-semibold text-zinc-100">
                      {step.action}
                    </span>
                    <StatusBadge status={step.status} size="sm" />
                  </div>

                  <div className="flex items-center gap-1.5 text-xs font-mono text-zinc-400">
                    <Clock className="h-3.5 w-3.5 text-zinc-400" />
                    <span>{step.duration_ms != null ? `${step.duration_ms}ms` : "-"}</span>
                  </div>
                </div>

                {/* Error diagnostics */}
                {step.error_message && (
                  <div className="mt-3 rounded-lg border border-rose-900/40 bg-rose-950/30 p-3 text-xs font-mono text-rose-300 flex items-start gap-2.5">
                    <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                    <div className="overflow-x-auto whitespace-pre-wrap">{step.error_message}</div>
                  </div>
                )}

                {/* Evidence screenshot */}
                {screenshotUrl && (
                  <div className="mt-3">
                    <div className="text-[11px] font-mono text-zinc-400 flex items-center gap-1.5 mb-1.5">
                      <Camera className="h-3.5 w-3.5 text-purple-400" />
                      <span>Captured Evidence</span>
                    </div>
                    <div 
                      onClick={() => setSelectedImage(screenshotUrl)}
                      className="group relative inline-block cursor-pointer overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900 max-w-sm"
                    >
                      <img
                        src={screenshotUrl}
                        alt={`Evidence for step ${step.step_index}`}
                        className="max-h-48 object-cover transition-transform group-hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
                        <Maximize2 className="h-5 w-5" />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

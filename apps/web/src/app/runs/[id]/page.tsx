"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { TestRun, TestCase } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StepTimeline } from "@/components/run/StepTimeline";
import { ConsoleLogsViewer } from "@/components/run/ConsoleLogsViewer";
import { 
  ArrowLeft, 
  Clock, 
  Download, 
  AlertTriangle, 
  RefreshCw, 
  Layers, 
  Terminal, 
  Ban, 
  Play,
  FileArchive
} from "lucide-react";

export default function RunDetailsPage() {
  const params = useParams();
  const runId = params.id as string;

  const [run, setRun] = useState<TestRun | null>(null);
  const [testCase, setTestCase] = useState<TestCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"steps" | "logs">("steps");
  const [error, setError] = useState<string | null>(null);

  const loadData = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      const runData = await api.getRun(runId);
      setRun(runData);

      if (runData.test_case_id) {
        api.getTestCase(runData.test_case_id)
          .then(setTestCase)
          .catch(() => {});
      }
    } catch (err: any) {
      setError(err.message || "Failed to load run details");
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    if (runId) {
      loadData(true);
    }
  }, [runId]);

  // Live auto-polling while the run is queued or running
  useEffect(() => {
    if (!run) return;
    if (run.status === "queued" || run.status === "running") {
      const timer = setInterval(() => {
        loadData(false);
      }, 1500);
      return () => clearInterval(timer);
    }
  }, [run?.status]);

  const handleCancel = async () => {
    if (!run) return;
    try {
      await api.cancelRun(run.id);
      await loadData(false);
    } catch (err: any) {
      alert(`Could not cancel run: ${err.message}`);
    }
  };

  if (loading && !run) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-6 w-32 bg-zinc-800 rounded"></div>
        <div className="h-36 bg-zinc-900 border border-zinc-800 rounded-xl"></div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="text-rose-400 font-mono text-sm">{error || "Run not found"}</div>
        <Link
          href="/runs"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-purple-400 hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>
      </div>
    );
  }

  const isAssertionFailure = run.status === "failed";
  const isExecutionError = run.status === "error";

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/runs"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Run History</span>
        </Link>
      </div>

      {/* Header Info Banner */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">
                Run #{run.id.slice(0, 8)}
              </h1>
              <StatusBadge status={run.status} />
            </div>

            {testCase && (
              <div className="mt-2 text-sm text-zinc-300 flex items-center gap-2">
                <span>Journey:</span>
                <span className="font-semibold text-purple-400">{testCase.name}</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {(run.status === "queued" || run.status === "running") && (
              <button
                onClick={handleCancel}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-900/60 bg-rose-950/30 text-xs font-medium text-rose-300 hover:bg-rose-900/40 transition-colors"
              >
                <Ban className="h-3.5 w-3.5" />
                <span>Cancel Run</span>
              </button>
            )}

            {run.trace_path && (
              <a
                href={api.getArtifactUrl(run.trace_path)}
                download
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-purple-500/40 bg-purple-950/30 text-xs font-medium text-purple-300 hover:bg-purple-900/40 transition-colors"
              >
                <FileArchive className="h-3.5 w-3.5" />
                <span>Download Playwright Trace</span>
              </a>
            )}

            <button
              onClick={() => loadData(false)}
              className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-zinc-200"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Diagnostics & Error summary */}
        {run.error_summary && (
          <div
            className={`rounded-lg border p-4 text-xs font-mono flex items-start gap-3 ${
              isAssertionFailure
                ? "border-rose-900/60 bg-rose-950/30 text-rose-300"
                : isExecutionError
                ? "border-amber-900/60 bg-amber-950/30 text-amber-300"
                : "border-zinc-800 bg-zinc-900/40 text-zinc-300"
            }`}
          >
            <AlertTriangle
              className={`h-4 w-4 shrink-0 mt-0.5 ${
                isAssertionFailure ? "text-rose-400" : "text-amber-400"
              }`}
            />
            <div>
              <div className="font-semibold uppercase tracking-wider text-[11px] mb-1">
                {isAssertionFailure
                  ? "Website State Assertion Failure"
                  : isExecutionError
                  ? "Browser Engine / Infrastructure Error"
                  : "Execution Summary"}
              </div>
              <div className="whitespace-pre-wrap">{run.error_summary}</div>
            </div>
          </div>
        )}

        {/* Metadata Footer */}
        <div className="pt-4 border-t border-zinc-800/80 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono text-zinc-400">
          <div>
            <span className="text-zinc-500 block text-[10px] uppercase">Duration</span>
            <span className="text-zinc-200 font-semibold">
              {run.duration_ms != null ? `${run.duration_ms}ms` : "-"}
            </span>
          </div>
          <div>
            <span className="text-zinc-500 block text-[10px] uppercase">Trigger</span>
            <span className="text-zinc-200 capitalize">{run.trigger_type}</span>
          </div>
          <div>
            <span className="text-zinc-500 block text-[10px] uppercase">Started</span>
            <span className="text-zinc-200">
              {run.started_at ? new Date(run.started_at).toLocaleTimeString() : "-"}
            </span>
          </div>
          <div>
            <span className="text-zinc-500 block text-[10px] uppercase">Finished</span>
            <span className="text-zinc-200">
              {run.finished_at ? new Date(run.finished_at).toLocaleTimeString() : "-"}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs: Step Timeline vs Console Logs */}
      <div className="space-y-4">
        <div className="flex border-b border-zinc-800 gap-4">
          <button
            onClick={() => setActiveTab("steps")}
            className={`pb-3 text-xs font-medium font-mono flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "steps"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Layers className="h-4 w-4" />
            <span>Step Execution Timeline ({run.step_results?.length || 0})</span>
          </button>
          <button
            onClick={() => setActiveTab("logs")}
            className={`pb-3 text-xs font-medium font-mono flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "logs"
                ? "border-purple-500 text-purple-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Terminal className="h-4 w-4" />
            <span>
              Console Logs & Crashes (
              {(run.console_logs_json?.length || 0) + (run.page_errors_json?.length || 0)}
              )
            </span>
          </button>
        </div>

        {activeTab === "steps" ? (
          <StepTimeline steps={run.step_results || []} />
        ) : (
          <ConsoleLogsViewer
            consoleLogs={run.console_logs_json || []}
            pageErrors={run.page_errors_json || []}
          />
        )}
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { TestRun } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  History, 
  RefreshCw, 
  Filter, 
  ChevronLeft, 
  ChevronRight, 
  ExternalLink,
  Ban
} from "lucide-react";

export default function RunsPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getRuns({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
      });
      setRuns(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load test runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, [page, statusFilter]);

  const handleCancel = async (runId: string) => {
    if (!confirm("Are you sure you want to cancel this running execution?")) return;
    try {
      await api.cancelRun(runId);
      await loadRuns();
    } catch (err: any) {
      alert(`Failed to cancel run: ${err.message}`);
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-100">Run History</h1>
          <p className="mt-1 text-xs text-zinc-400">
            Audit log of autonomous browser test executions, screenshots, and visual QA results.
          </p>
        </div>

        <button
          onClick={loadRuns}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#232630] bg-zinc-900/90 text-xs font-mono text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 text-zinc-400 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <Filter className="h-4 w-4 text-zinc-400" />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-[#232630] bg-[#13151b] px-3 py-1.5 text-xs font-mono text-zinc-300 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 transition-colors"
        >
          <option value="">All Statuses</option>
          <option value="passed">Passed</option>
          <option value="failed">Failed (Assertion Mismatch)</option>
          <option value="error">Error (Execution Error)</option>
          <option value="running">Running</option>
          <option value="queued">Queued</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <span className="text-xs font-mono text-zinc-500">
          Total: {total} runs
        </span>
      </div>

      {/* Runs Table */}
      {loading ? (
        <div className="h-64 bg-[#13151b] border border-[#232630] rounded-xl animate-pulse"></div>
      ) : runs.length > 0 ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-[#232630] bg-[#13151b] overflow-hidden shadow-subtle">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#232630] text-zinc-400 font-mono bg-[#0f1116]">
                  <th className="py-3 px-4 font-medium">Run ID</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Trigger</th>
                  <th className="py-3 px-4 font-medium">Duration</th>
                  <th className="py-3 px-4 font-medium">Executed At</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232630]/60 font-mono">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-zinc-800/20 transition-colors">
                    <td className="py-3 px-4">
                      <Link
                        href={`/runs/${r.id}`}
                        className="font-semibold text-zinc-200 hover:text-white flex items-center gap-1.5 transition-colors"
                      >
                        <span>{r.id.slice(0, 8)}...</span>
                        <ExternalLink className="h-3 w-3 text-zinc-500" />
                      </Link>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={r.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 capitalize text-zinc-400">
                      {r.trigger_type}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {r.duration_ms != null ? `${r.duration_ms}ms` : "-"}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {(r.status === "queued" || r.status === "running") && (
                        <button
                          onClick={() => handleCancel(r.id)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-rose-900/60 text-[11px] text-rose-400 bg-rose-950/20 hover:bg-rose-950/40"
                        >
                          <Ban className="h-3 w-3" />
                          <span>Cancel</span>
                        </button>
                      )}
                      {r.status !== "queued" && r.status !== "running" && (
                        <Link
                          href={`/runs/${r.id}`}
                          className="text-xs text-zinc-300 hover:text-white font-medium transition-colors"
                        >
                          Details
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-xs font-mono text-zinc-400 px-1">
            <div>
              Page {page} of {totalPages}
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-1.5 rounded border border-[#232630] bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1.5 rounded border border-[#232630] bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={History}
          title="No test runs recorded"
          description="Trigger an automated test case or run an autonomous audit to inspect live Playwright execution records."
        />
      )}
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { TestRun, RunStatus } from "@/lib/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  History, 
  Filter, 
  RefreshCw, 
  ExternalLink, 
  Ban, 
  ChevronLeft, 
  ChevronRight,
  Clock
} from "lucide-react";

export default function RunsPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const res = await api.getRuns({
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setRuns(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, [page, statusFilter]);

  const handleCancel = async (id: string) => {
    try {
      await api.cancelRun(id);
      await loadRuns();
    } catch (err: any) {
      alert(`Could not cancel run: ${err.message}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Run History</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Audit log of all manual and scheduled browser test executions.
          </p>
        </div>

        <button
          onClick={loadRuns}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-mono text-zinc-300 hover:bg-zinc-800 transition-colors"
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
          className="rounded-lg border border-zinc-800 bg-[#0f0f12] px-3 py-1.5 text-xs font-mono text-zinc-300 focus:border-purple-500 focus:outline-none"
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
        <div className="h-64 bg-zinc-900/40 border border-zinc-800 rounded-xl animate-pulse"></div>
      ) : runs.length > 0 ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-400 font-mono bg-[#141418]">
                  <th className="py-3 px-4 font-medium">Run ID</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Trigger</th>
                  <th className="py-3 px-4 font-medium">Duration</th>
                  <th className="py-3 px-4 font-medium">Executed At</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800 font-mono">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-zinc-800/20">
                    <td className="py-3 px-4">
                      <Link
                        href={`/runs/${r.id}`}
                        className="font-semibold text-zinc-200 hover:text-purple-400 flex items-center gap-1.5"
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
                          className="text-xs text-purple-400 hover:text-purple-300 font-medium"
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
                className="p-1.5 rounded border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-1.5 rounded border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={History}
          title="No execution runs found"
          description="Trigger a test case to execute journeys in Chromium and inspect real results."
        />
      )}
    </div>
  );
}

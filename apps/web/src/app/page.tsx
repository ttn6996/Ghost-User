"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { OverviewStats } from "@/lib/types";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  FolderKanban, 
  PlayCircle, 
  CheckCircle2, 
  Percent, 
  AlertTriangle, 
  ArrowRight, 
  RefreshCw,
  Plus
} from "lucide-react";

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getOverviewStats();
      setStats(data);
    } catch (err: any) {
      setError(err.message || "Failed to load statistics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading && !stats) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-zinc-800 rounded"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-zinc-900 border border-zinc-800 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Testing Overview</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Real-time execution metrics and test reliability across active projects.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-mono text-zinc-300 hover:bg-zinc-800 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-zinc-400 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <Link
            href="/projects"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            <span>New Project</span>
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4 text-xs font-mono text-rose-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
          <span>Error loading metrics: {error}</span>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Projects"
          value={stats?.total_projects ?? 0}
          subtitle="Monitored target origins"
          icon={FolderKanban}
        />
        <StatCard
          title="Test Cases"
          value={stats?.total_test_cases ?? 0}
          subtitle="Automated journey suites"
          icon={PlayCircle}
        />
        <StatCard
          title="Total Test Runs"
          value={stats?.total_runs ?? 0}
          subtitle={`${stats?.passed_runs ?? 0} passed, ${stats?.failed_runs ?? 0} failed`}
          icon={CheckCircle2}
        />
        <StatCard
          title="Pass Rate"
          value={`${stats?.pass_rate_percentage ?? 0}%`}
          subtitle="Overall assertion success"
          icon={Percent}
        />
      </div>

      {/* Two Column Layout: Recent Runs & Recent Failures */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Runs Table */}
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <PlayCircle className="h-4 w-4 text-purple-400" />
              <span>Recent Test Runs</span>
            </h2>
            <Link
              href="/runs"
              className="text-xs text-purple-400 hover:text-purple-300 font-mono flex items-center gap-1"
            >
              <span>View all</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {stats && stats.recent_runs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400 font-mono">
                    <th className="pb-2 font-medium">Run ID</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Duration</th>
                    <th className="pb-2 font-medium text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 font-mono">
                  {stats.recent_runs.map((r) => (
                    <tr key={r.id} className="hover:bg-zinc-800/20">
                      <td className="py-2.5 font-semibold text-zinc-200">
                        <Link href={`/runs/${r.id}`} className="hover:text-purple-400">
                          {r.id.slice(0, 8)}...
                        </Link>
                      </td>
                      <td className="py-2.5">
                        <StatusBadge status={r.status} size="sm" />
                      </td>
                      <td className="py-2.5 text-zinc-400">
                        {r.duration_ms != null ? `${r.duration_ms}ms` : "-"}
                      </td>
                      <td className="py-2.5 text-right text-zinc-400">
                        {new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-zinc-400">
              No runs executed yet. Trigger a test case to see real history.
            </div>
          )}
        </div>

        {/* Recent Failures Feed */}
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-400" />
              <span>Recent Failures & Errors</span>
            </h2>
          </div>

          {stats && stats.recent_failures.length > 0 ? (
            <div className="space-y-3">
              {stats.recent_failures.map((f) => (
                <div
                  key={f.id}
                  className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-3 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/runs/${f.id}`}
                      className="font-mono font-semibold text-rose-300 hover:underline"
                    >
                      Run #{f.id.slice(0, 8)}
                    </Link>
                    <StatusBadge status={f.status} size="sm" />
                  </div>
                  <div className="font-mono text-zinc-300 text-[11px] truncate">
                    {f.error_summary || "Unknown failure occurred"}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-zinc-400">
              All clear! No recent assertion failures or errors detected.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

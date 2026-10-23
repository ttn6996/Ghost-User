"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Schedule, TestCase } from "@/lib/types";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  CalendarClock, 
  Plus, 
  Trash2, 
  Power, 
  Clock, 
  AlertCircle 
} from "lucide-react";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form
  const [selectedTestCaseId, setSelectedTestCaseId] = useState("");
  const [intervalSeconds, setIntervalSeconds] = useState(3600);
  const [cronExpression, setCronExpression] = useState("");
  const [mode, setMode] = useState<"interval" | "cron">("interval");

  const loadData = async () => {
    try {
      setLoading(true);
      const [schedList, tcList] = await Promise.all([
        api.getSchedules(),
        api.getTestCases(),
      ]);
      setSchedules(schedList);
      setTestCases(tcList);
      if (tcList.length > 0 && !selectedTestCaseId) {
        setSelectedTestCaseId(tcList[0].id);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggle = async (id: string) => {
    try {
      const updated = await api.toggleSchedule(id);
      setSchedules(schedules.map((s) => (s.id === id ? updated : s)));
    } catch (err: any) {
      alert(`Could not toggle schedule: ${err.message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this schedule?")) return;
    try {
      await api.deleteSchedule(id);
      setSchedules(schedules.filter((s) => s.id !== id));
    } catch (err: any) {
      alert(`Could not delete schedule: ${err.message}`);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTestCaseId) {
      setError("Please select a test case");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const payload = {
        test_case_id: selectedTestCaseId,
        interval_seconds: mode === "interval" ? Number(intervalSeconds) : undefined,
        cron_expression: mode === "cron" ? cronExpression : undefined,
        enabled: true,
      };

      await api.createSchedule(payload);
      setModalOpen(false);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create schedule");
    } finally {
      setSubmitting(false);
    }
  };

  const getTestCaseName = (id: string) => {
    const tc = testCases.find((x) => x.id === id);
    return tc ? tc.name : id.slice(0, 8);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Recurring Schedules</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Automate test executions at fixed intervals or cron schedules.
          </p>
        </div>

        <button
          onClick={() => {
            setError(null);
            setModalOpen(true);
          }}
          disabled={testCases.length === 0}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          <span>New Schedule</span>
        </button>
      </div>

      {loading ? (
        <div className="h-64 bg-zinc-900/40 border border-zinc-800 rounded-xl animate-pulse"></div>
      ) : schedules.length > 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 font-mono bg-[#141418]">
                <th className="py-3 px-4 font-medium">Test Case</th>
                <th className="py-3 px-4 font-medium">Frequency</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium">Next Execution</th>
                <th className="py-3 px-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 font-mono">
              {schedules.map((s) => (
                <tr key={s.id} className="hover:bg-zinc-800/20">
                  <td className="py-3 px-4 font-semibold text-zinc-200">
                    {getTestCaseName(s.test_case_id)}
                  </td>
                  <td className="py-3 px-4 text-purple-400">
                    {s.interval_seconds
                      ? `Every ${s.interval_seconds >= 3600 ? `${s.interval_seconds / 3600}h` : `${s.interval_seconds}s`}`
                      : s.cron_expression || "Custom"}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border ${
                        s.enabled
                          ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/40"
                          : "bg-zinc-900 text-zinc-500 border-zinc-800"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${s.enabled ? "bg-emerald-400" : "bg-zinc-600"}`} />
                      <span>{s.enabled ? "Active" : "Paused"}</span>
                    </span>
                  </td>
                  <td className="py-3 px-4 text-zinc-400">
                    {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "-"}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="inline-flex items-center gap-2">
                      <button
                        onClick={() => handleToggle(s.id)}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors border ${
                          s.enabled
                            ? "bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700"
                            : "bg-purple-950/40 border-purple-800/40 text-purple-300 hover:bg-purple-900/40"
                        }`}
                      >
                        <Power className="h-3 w-3" />
                        <span>{s.enabled ? "Pause" : "Enable"}</span>
                      </button>
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                        title="Delete schedule"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon={CalendarClock}
          title="No scheduled test runs"
          description="Schedule automated background test runs to run periodically without manual triggering."
          actionLabel={testCases.length > 0 ? "Create Schedule" : undefined}
          onAction={() => setModalOpen(true)}
        />
      )}

      {/* Create Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create Recurring Test Schedule"
        description="Choose how frequently to run an automated browser journey."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          {error && (
            <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-3 text-xs font-mono text-rose-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">Target Test Case *</label>
            <select
              required
              value={selectedTestCaseId}
              onChange={(e) => setSelectedTestCaseId(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs font-mono text-zinc-200 focus:border-purple-500 focus:outline-none"
            >
              {testCases.map((tc) => (
                <option key={tc.id} value={tc.id}>
                  {tc.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">Schedule Mode</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("interval")}
                className={`flex-1 py-1.5 rounded-lg border text-xs font-mono transition-colors ${
                  mode === "interval"
                    ? "bg-purple-950/40 border-purple-600/60 text-purple-300"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                Fixed Interval
              </button>
              <button
                type="button"
                onClick={() => setMode("cron")}
                className={`flex-1 py-1.5 rounded-lg border text-xs font-mono transition-colors ${
                  mode === "cron"
                    ? "bg-purple-950/40 border-purple-600/60 text-purple-300"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                Cron Expression
              </button>
            </div>
          </div>

          {mode === "interval" ? (
            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Interval (Seconds)
              </label>
              <select
                value={intervalSeconds}
                onChange={(e) => setIntervalSeconds(Number(e.target.value))}
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs font-mono text-zinc-200 focus:border-purple-500 focus:outline-none"
              >
                <option value={60}>Every 1 minute (60s)</option>
                <option value={300}>Every 5 minutes (300s)</option>
                <option value={900}>Every 15 minutes (900s)</option>
                <option value={3600}>Every 1 hour (3600s)</option>
                <option value={86400}>Every 24 hours (86400s)</option>
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Cron Expression (Standard 5-field)
              </label>
              <input
                type="text"
                value={cronExpression}
                onChange={(e) => setCronExpression(e.target.value)}
                placeholder="0 * * * * (hourly)"
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs font-mono text-zinc-200 focus:border-purple-500 focus:outline-none"
              />
            </div>
          )}

          <div className="pt-3 flex justify-end gap-2 border-t border-zinc-800">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white shadow-sm disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Create Schedule"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

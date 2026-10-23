"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { TestCase, Project } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  PlayCircle, 
  Plus, 
  Play, 
  Edit, 
  Trash2, 
  Filter,
  ArrowRight
} from "lucide-react";

export default function TestCasesPage() {
  const router = useRouter();
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);

  const loadData = async (projectId = "") => {
    try {
      setLoading(true);
      const [tcList, projList] = await Promise.all([
        api.getTestCases(projectId || undefined),
        api.getProjects(),
      ]);
      setTestCases(tcList);
      setProjects(projList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(selectedProjectId);
  }, [selectedProjectId]);

  const handleRun = async (testCaseId: string) => {
    try {
      setRunningId(testCaseId);
      const run = await api.triggerRun(testCaseId);
      router.push(`/runs/${run.id}`);
    } catch (err: any) {
      alert(`Failed to trigger test: ${err.message}`);
      setRunningId(null);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete test case "${name}"?`)) return;
    try {
      await api.deleteTestCase(id);
      setTestCases(testCases.filter((t) => t.id !== id));
    } catch (err: any) {
      alert(`Could not delete test case: ${err.message}`);
    }
  };

  const getProjectName = (projectId: string) => {
    const p = projects.find((x) => x.id === projectId);
    return p ? p.name : projectId.slice(0, 8);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Test Cases</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Automated browser user journeys and validation criteria.
          </p>
        </div>

        <Link
          href="/tests/new"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm"
        >
          <Plus className="h-4 w-4" />
          <span>New Test Case</span>
        </Link>
      </div>

      {/* Project Filter */}
      <div className="flex items-center gap-3">
        <Filter className="h-4 w-4 text-zinc-400" />
        <select
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          className="rounded-lg border border-zinc-800 bg-[#0f0f12] px-3 py-1.5 text-xs font-mono text-zinc-300 focus:border-purple-500 focus:outline-none"
        >
          <option value="">All Projects</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="h-64 bg-zinc-900/40 border border-zinc-800 rounded-xl animate-pulse"></div>
      ) : testCases.length > 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-400 font-mono bg-[#141418]">
                <th className="py-3 px-4 font-medium">Test Name</th>
                <th className="py-3 px-4 font-medium">Project</th>
                <th className="py-3 px-4 font-medium">Step Count</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 font-mono">
              {testCases.map((tc) => (
                <tr key={tc.id} className="hover:bg-zinc-800/20">
                  <td className="py-3 px-4">
                    <div className="font-semibold text-zinc-200">{tc.name}</div>
                    {tc.description && (
                      <div className="text-[11px] text-zinc-400 font-sans mt-0.5 truncate max-w-sm">
                        {tc.description}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-4 text-purple-400">
                    <Link href={`/projects/${tc.project_id}`} className="hover:underline">
                      {getProjectName(tc.project_id)}
                    </Link>
                  </td>
                  <td className="py-3 px-4 text-zinc-400">
                    {tc.definition_json?.steps?.length ?? 0} actions
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex px-2 py-0.5 rounded text-[10px] ${
                      tc.enabled ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/40" : "bg-zinc-800 text-zinc-400"
                    }`}>
                      {tc.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="inline-flex items-center gap-2">
                      <button
                        onClick={() => handleRun(tc.id)}
                        disabled={runningId === tc.id}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-purple-600/20 border border-purple-500/40 text-purple-300 hover:bg-purple-600/30 text-xs transition-colors"
                      >
                        <Play className="h-3 w-3 fill-current" />
                        <span>{runningId === tc.id ? "Queuing..." : "Run"}</span>
                      </button>
                      <Link
                        href={`/tests/${tc.id}/edit`}
                        className="p-1 text-zinc-400 hover:text-zinc-200 transition-colors"
                        title="Edit Test Case"
                      >
                        <Edit className="h-3.5 w-3.5" />
                      </Link>
                      <button
                        onClick={() => handleDelete(tc.id, tc.name)}
                        className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                        title="Delete Test Case"
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
          icon={PlayCircle}
          title="No test cases found"
          description="Build your first automated test definition using the step builder."
          actionLabel="Create Test Case"
          onAction={() => router.push("/tests/new")}
        />
      )}
    </div>
  );
}

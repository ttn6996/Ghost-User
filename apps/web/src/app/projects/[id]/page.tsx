"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Project, TestCase } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  FolderKanban, 
  Globe, 
  PlayCircle, 
  Plus, 
  ArrowLeft, 
  ExternalLink, 
  Trash2, 
  Play,
  Calendar,
  AlertCircle
} from "lucide-react";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningTestId, setRunningTestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [projData, tcData] = await Promise.all([
        api.getProject(projectId),
        api.getTestCases(projectId),
      ]);
      setProject(projData);
      setTestCases(tcData);
    } catch (err: any) {
      setError(err.message || "Failed to load project details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  const handleRunTest = async (testCaseId: string) => {
    try {
      setRunningTestId(testCaseId);
      const run = await api.triggerRun(testCaseId);
      router.push(`/runs/${run.id}`);
    } catch (err: any) {
      alert(`Failed to trigger test run: ${err.message}`);
      setRunningTestId(null);
    }
  };

  const handleDeleteTestCase = async (id: string, name: string) => {
    if (!window.confirm(`Delete test case "${name}"?`)) return;
    try {
      await api.deleteTestCase(id);
      setTestCases(testCases.filter((tc) => tc.id !== id));
    } catch (err: any) {
      alert(`Could not delete test case: ${err.message}`);
    }
  };

  if (loading && !project) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-6 w-32 bg-zinc-800 rounded"></div>
        <div className="h-24 bg-zinc-900 border border-zinc-800 rounded-xl"></div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="text-rose-400 font-mono text-sm">{error || "Project not found"}</div>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-purple-400 hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Projects</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Back button */}
      <div>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Projects</span>
        </Link>
      </div>

      {/* Project Header Card */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-100">{project.name}</h1>
            <div className="mt-2 flex items-center gap-2 text-xs font-mono text-purple-400">
              <Globe className="h-4 w-4" />
              <a
                href={project.base_url}
                target="_blank"
                rel="noreferrer"
                className="hover:underline flex items-center gap-1"
              >
                <span>{project.base_url}</span>
                <ExternalLink className="h-3 w-3 text-zinc-500" />
              </a>
            </div>
          </div>

          <Link
            href={`/tests/new?project_id=${project.id}`}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            <span>Create Test Case</span>
          </Link>
        </div>

        {project.description && (
          <p className="text-xs text-zinc-400 max-w-2xl">{project.description}</p>
        )}

        <div className="pt-4 border-t border-zinc-800/80 flex items-center gap-6 text-xs font-mono text-zinc-400">
          <div>
            Total Tests: <span className="text-zinc-200 font-semibold">{testCases.length}</span>
          </div>
          <div>
            Created: <span className="text-zinc-300">{new Date(project.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>

      {/* Test Cases in this Project */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <PlayCircle className="h-4 w-4 text-purple-400" />
            <span>Project Test Cases ({testCases.length})</span>
          </h2>
        </div>

        {testCases.length > 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-400 font-mono bg-[#141418]">
                  <th className="py-3 px-4 font-medium">Test Case</th>
                  <th className="py-3 px-4 font-medium">Steps</th>
                  <th className="py-3 px-4 font-medium">Enabled</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800 font-mono">
                {testCases.map((tc) => (
                  <tr key={tc.id} className="hover:bg-zinc-800/20">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-zinc-200">{tc.name}</div>
                      {tc.description && (
                        <div className="text-[11px] text-zinc-400 font-sans mt-0.5 truncate max-w-md">
                          {tc.description}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-zinc-400">
                      {tc.definition_json?.steps?.length ?? 0} actions
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex px-2 py-0.5 rounded text-[10px] ${
                        tc.enabled ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/40" : "bg-zinc-800 text-zinc-400"
                      }`}>
                        {tc.enabled ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex items-center gap-2">
                        <button
                          onClick={() => handleRunTest(tc.id)}
                          disabled={runningTestId === tc.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-purple-600/20 border border-purple-500/40 text-purple-300 hover:bg-purple-600/30 text-xs transition-colors"
                        >
                          <Play className="h-3 w-3 fill-current" />
                          <span>{runningTestId === tc.id ? "Queuing..." : "Run"}</span>
                        </button>
                        <Link
                          href={`/tests/${tc.id}/edit`}
                          className="px-2 py-1 rounded border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-xs"
                        >
                          Edit
                        </Link>
                        <button
                          onClick={() => handleDeleteTestCase(tc.id, tc.name)}
                          className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
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
            title="No test cases yet"
            description="Add a browser test journey to test user flows on this website."
            actionLabel="Create Test Case"
            onAction={() => router.push(`/tests/new?project_id=${project.id}`)}
          />
        )}
      </div>
    </div>
  );
}

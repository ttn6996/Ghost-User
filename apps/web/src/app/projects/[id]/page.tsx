"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { 
  Project, 
  TestCase, 
  DiscoveryReport, 
  StepAction,
  DevServerInfo,
  SourceScanResult,
  AutonomousAuditResponse
} from "@/lib/types";
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
  AlertCircle,
  Compass,
  Sparkles,
  CheckCircle2,
  FileText,
  Layers,
  Bug,
  RefreshCw,
  Terminal,
  Code,
  Server,
  PlaySquare,
  Square,
  Shield,
  Check,
  Loader2,
  AlertTriangle,
  ArrowRight,
  FolderGit2
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

  // Tabs: 'tests' | 'source' | 'discovery'
  const [activeTab, setActiveTab] = useState<"tests" | "source" | "discovery">("tests");

  // Discovery state
  const [discoveryReport, setDiscoveryReport] = useState<DiscoveryReport | null>(null);
  const [crawling, setCrawling] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);
  const [savingTestIdx, setSavingTestIdx] = useState<number | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  // Local Source & Dev Server state
  const [sourcePathInput, setSourcePathInput] = useState("");
  const [savingPath, setSavingPath] = useState(false);
  const [savePathMsg, setSavePathMsg] = useState<string | null>(null);
  const [scanningSource, setScanningSource] = useState(false);
  const [scanResult, setScanResult] = useState<SourceScanResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // Mode B Dev Server state
  const [devServer, setDevServer] = useState<DevServerInfo | null>(null);
  const [startingServer, setStartingServer] = useState(false);
  const [stoppingServer, setStoppingServer] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [customCommand, setCustomCommand] = useState("");
  const [customPort, setCustomPort] = useState("");

  // Autonomous Audit state
  const [auditing, setAuditing] = useState(false);
  const [auditResult, setAuditResult] = useState<AutonomousAuditResponse | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [projData, tcData, latestDiscovery, serverStatus] = await Promise.all([
        api.getProject(projectId),
        api.getTestCases(projectId),
        api.getLatestDiscovery(projectId).catch(() => null),
        api.getDevServerStatus(projectId).catch(() => null),
      ]);
      setProject(projData);
      setTestCases(tcData);
      if (projData.source_code_path) {
        setSourcePathInput(projData.source_code_path);
      }
      if (latestDiscovery) {
        setDiscoveryReport(latestDiscovery);
      }
      if (serverStatus) {
        setDevServer(serverStatus);
      }
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

  const handleStartDiscovery = async () => {
    try {
      setCrawling(true);
      setCrawlError(null);
      setSaveSuccessMsg(null);
      const report = await api.discoverProject(projectId, 15);
      setDiscoveryReport(report);
    } catch (err: any) {
      setCrawlError(err.message || "Quá trình quét và khám phá website thất bại.");
    } finally {
      setCrawling(false);
    }
  };

  const handleSaveDiscoveredTest = async (
    suggestedTest: { name: string; description?: string; steps: StepAction[] },
    idx: number
  ) => {
    try {
      setSavingTestIdx(idx);
      setSaveSuccessMsg(null);
      const created = await api.saveDiscoveredTest(projectId, suggestedTest);
      setTestCases((prev) => [created, ...prev]);
      setSaveSuccessMsg(`Đã thêm thành công kịch bản "${created.name}" vào dự án!`);
    } catch (err: any) {
      alert(`Không thể lưu kịch bản: ${err.message}`);
    } finally {
      setSavingTestIdx(null);
    }
  };

  const handleSaveSourcePath = async () => {
    if (!sourcePathInput.trim()) return;
    try {
      setSavingPath(true);
      setSavePathMsg(null);
      setScanError(null);
      await api.setSourceDirectory(projectId, sourcePathInput.trim());
      setSavePathMsg("Đã liên kết thành công thư mục source code!");
      const updatedProj = await api.getProject(projectId);
      setProject(updatedProj);
    } catch (err: any) {
      setScanError(err.message || "Không thể cấu hình thư mục source code");
    } finally {
      setSavingPath(false);
    }
  };

  const handleScanSource = async () => {
    try {
      setScanningSource(true);
      setScanError(null);
      const res = await api.scanSource(projectId);
      setScanResult(res);
      if (res.start_command && !customCommand) {
        setCustomCommand(res.start_command);
      }
    } catch (err: any) {
      setScanError(err.message || "Không thể phân tích source code");
    } finally {
      setScanningSource(false);
    }
  };

  const handleStartDevServer = async () => {
    try {
      setStartingServer(true);
      setServerError(null);
      const info = await api.startDevServer(projectId, {
        command: customCommand || undefined,
        port: customPort ? parseInt(customPort, 10) : undefined,
      });
      setDevServer(info);
      if (info.target_url) {
        const updatedProj = await api.getProject(projectId);
        setProject(updatedProj);
      }
    } catch (err: any) {
      setServerError(err.message || "Không thể khởi động dev server");
    } finally {
      setStartingServer(false);
    }
  };

  const handleStopDevServer = async () => {
    try {
      setStoppingServer(true);
      await api.stopDevServer(projectId);
      const status = await api.getDevServerStatus(projectId);
      setDevServer(status);
    } catch (err: any) {
      alert(`Không thể dừng dev server: ${err.message}`);
    } finally {
      setStoppingServer(false);
    }
  };

  const handleRunAutonomousAudit = async () => {
    try {
      setAuditing(true);
      setAuditError(null);
      setAuditResult(null);
      const res = await api.runAutonomousAudit(projectId, {
        auto_start_server: true,
        max_pages: 15,
        run_form_tests: true,
      });
      setAuditResult(res);
      // Reload project test cases & discovery report
      const [updatedProj, tcData, latestDiscovery, serverStatus] = await Promise.all([
        api.getProject(projectId),
        api.getTestCases(projectId),
        api.getLatestDiscovery(projectId).catch(() => null),
        api.getDevServerStatus(projectId).catch(() => null),
      ]);
      setProject(updatedProj);
      setTestCases(tcData);
      if (latestDiscovery) setDiscoveryReport(latestDiscovery);
      if (serverStatus) setDevServer(serverStatus);
    } catch (err: any) {
      setAuditError(err.message || "Quá trình Autonomous UI Audit thất bại.");
    } finally {
      setAuditing(false);
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
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-100">{project.name}</h1>
              {devServer?.is_running && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-mono text-[11px]">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span>Dev Server Online</span>
                </span>
              )}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs font-mono">
              <div className="flex items-center gap-1.5 text-purple-400">
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

              {project.source_code_path && (
                <div className="flex items-center gap-1.5 text-zinc-400 border-l border-zinc-800 pl-4">
                  <FolderGit2 className="h-3.5 w-3.5 text-blue-400" />
                  <span className="truncate max-w-sm text-zinc-300">{project.source_code_path}</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                setActiveTab("source");
                handleRunAutonomousAudit();
              }}
              disabled={auditing}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-md transition disabled:opacity-50"
            >
              {auditing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 text-purple-200" />
              )}
              <span>{auditing ? "Đang Audit..." : "Chạy Autonomous UI Audit"}</span>
            </button>

            <Link
              href={`/tests/new?project_id=${project.id}`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 border border-zinc-700/60 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              <span>Create Test</span>
            </Link>
          </div>
        </div>

        {project.description && (
          <p className="text-xs text-zinc-400 max-w-2xl">{project.description}</p>
        )}

        <div className="pt-4 border-t border-zinc-800/80 flex flex-wrap items-center gap-6 text-xs font-mono text-zinc-400">
          <div>
            Total Tests: <span className="text-zinc-200 font-semibold">{testCases.length}</span>
          </div>
          <div>
            Discovered Pages: <span className="text-zinc-200 font-semibold">{discoveryReport?.pages_count ?? 0}</span>
          </div>
          <div>
            Loopback Target: <span className={project.allow_local_loopback ? "text-emerald-400 font-semibold" : "text-zinc-400"}>{project.allow_local_loopback ? "Permitted" : "Strict SSRF Guard"}</span>
          </div>
          <div>
            Created: <span className="text-zinc-300">{new Date(project.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab("tests")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-medium transition ${
            activeTab === "tests"
              ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
          }`}
        >
          <PlayCircle className="h-4 w-4" />
          <span>Test Cases ({testCases.length})</span>
        </button>

        <button
          onClick={() => {
            setActiveTab("source");
            if (!scanResult && project.source_code_path) {
              handleScanSource();
            }
          }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-medium transition ${
            activeTab === "source"
              ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
          }`}
        >
          <Code className="h-4 w-4" />
          <span>Local Source & Dev Server</span>
          {project.source_code_path && (
            <span className="px-1.5 py-0.5 rounded-full bg-blue-500/20 text-[10px] text-blue-300 border border-blue-500/30">
              Linked
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("discovery")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-medium transition ${
            activeTab === "discovery"
              ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
          }`}
        >
          <Compass className="h-4 w-4" />
          <span>Auto-Discovery & Crawler</span>
          {discoveryReport && (
            <span className="px-1.5 py-0.2 rounded-full bg-purple-500/30 text-[10px] text-purple-200">
              {discoveryReport.pages_count} trang
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: Test Cases */}
      {activeTab === "tests" && (
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
              title="Chưa có kịch bản kiểm thử nào"
              description="Bạn có thể mở tab Local Source để chạy Autonomous Audit hoặc tạo kịch bản mới."
              actionLabel="Tạo Test Case mới"
              onAction={() => router.push(`/tests/new?project_id=${project.id}`)}
            />
          )}
        </div>
      )}

      {/* TAB 2: Local Source & Dev Server */}
      {activeTab === "source" && (
        <div className="space-y-6">
          {/* Autonomous Audit Hero Banner */}
          <div className="rounded-xl border border-purple-500/30 bg-gradient-to-r from-purple-950/30 via-[#0f0f12] to-indigo-950/20 p-6 space-y-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-purple-400" />
                  <h3 className="text-base font-semibold text-zinc-100">
                    Autonomous UI & Source Code Audit
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono border border-purple-500/30">
                    Mode B Autonomous
                  </span>
                </div>
                <p className="text-xs text-zinc-400 max-w-2xl leading-relaxed">
                  Tự động quét cấu trúc AST source code, khởi động background dev server, &quot;bò&quot; crawl toàn bộ giao diện bằng Playwright, tự động sinh test form với dữ liệu mẫu tagged (<code className="text-purple-300 font-mono">AUTOQA_...</code>) và tự động dọn dẹp cơ sở dữ liệu sau kiểm thử.
                </p>
              </div>

              <button
                type="button"
                onClick={handleRunAutonomousAudit}
                disabled={auditing}
                className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center gap-2 transition disabled:opacity-50 shadow-md shrink-0"
              >
                {auditing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4 text-purple-200" />
                )}
                <span>{auditing ? "Đang chạy Autonomous Audit..." : "Bắt đầu Audit Toàn Diện"}</span>
              </button>
            </div>

            {auditing && (
              <div className="rounded-lg border border-purple-500/40 bg-purple-950/40 p-4 text-xs font-mono text-purple-200 flex items-center gap-3 animate-pulse">
                <Loader2 className="h-5 w-5 animate-spin text-purple-400 shrink-0" />
                <div>
                  <div className="font-semibold">Đang thực thi quy trình Autonomous UI Audit...</div>
                  <div className="text-[11px] text-purple-300/80 mt-0.5">
                    1. AST Source scan &rarr; 2. Dev server launch &rarr; 3. Seeded Playwright crawl &rarr; 4. Form tests execution &rarr; 5. Tagged data teardown.
                  </div>
                </div>
              </div>
            )}

            {auditError && (
              <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-3 text-xs font-mono text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{auditError}</span>
              </div>
            )}

            {auditResult && (
              <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{auditResult.audit_summary}</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-zinc-300 pt-2 border-t border-emerald-900/40 text-[11px]">
                  <div>
                    <span className="text-zinc-500">Framework:</span>{" "}
                    <span className="text-zinc-200 font-semibold">{auditResult.frameworks.join(", ") || "Generic Web"}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Pages Audited:</span>{" "}
                    <span className="text-zinc-200 font-semibold">{auditResult.pages_audited_count}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Forms Tested:</span>{" "}
                    <span className="text-zinc-200 font-semibold">{auditResult.forms_detected_count}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Tests Passed:</span>{" "}
                    <span className="text-emerald-400 font-semibold">{auditResult.tests_passed_count} / {auditResult.tests_executed_count}</span>
                  </div>
                </div>

                {auditResult.test_runs.length > 0 && (
                  <div className="pt-2 border-t border-emerald-900/40 space-y-1.5">
                    <div className="text-[11px] text-zinc-400 font-semibold">Kịch bản đã tự động sinh & chạy:</div>
                    {auditResult.test_runs.map((r) => (
                      <div key={r.id} className="flex items-center justify-between p-2 rounded bg-zinc-900/60 border border-zinc-800 text-[11px]">
                        <span className="text-zinc-200">{r.name}</span>
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                            r.status === "passed" ? "bg-emerald-950/60 text-emerald-400" : "bg-rose-950/60 text-rose-400"
                          }`}>
                            {r.status}
                          </span>
                          <Link href={`/runs/${r.id}`} className="text-purple-400 hover:underline flex items-center gap-0.5">
                            <span>Chi tiết</span>
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 2-Column Grid: Source Path & Dev Server */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Card 1: Local Source Path & AST Inspector */}
            <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <FolderGit2 className="h-4 w-4 text-blue-400" />
                  <span>Local Source Code Directory</span>
                </h3>
                <span className="text-[10px] font-mono text-zinc-500">AST Static Analysis</span>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-mono text-zinc-400">
                  Thư mục mã nguồn cục bộ (Local Directory Path):
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={sourcePathInput}
                    onChange={(e) => setSourcePathInput(e.target.value)}
                    placeholder="e.g. D:\code\my-app or /home/user/app"
                    className="flex-1 rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
                  />
                  <button
                    onClick={handleSaveSourcePath}
                    disabled={savingPath || !sourcePathInput}
                    className="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-mono text-zinc-200 border border-zinc-700/60 transition disabled:opacity-50 shrink-0"
                  >
                    {savingPath ? "Saving..." : "Lưu"}
                  </button>
                </div>
              </div>

              {savePathMsg && (
                <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-2.5 text-xs font-mono text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  <span>{savePathMsg}</span>
                </div>
              )}

              {scanError && (
                <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-2.5 text-xs font-mono text-rose-300 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                  <span>{scanError}</span>
                </div>
              )}

              <div className="pt-2 flex items-center justify-between border-t border-zinc-800">
                <button
                  onClick={handleScanSource}
                  disabled={scanningSource || !project.source_code_path}
                  className="px-3.5 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/40 text-xs font-mono font-medium flex items-center gap-1.5 transition disabled:opacity-50"
                >
                  <Code className={`h-3.5 w-3.5 ${scanningSource ? "animate-spin" : ""}`} />
                  <span>{scanningSource ? "Đang phân tích AST..." : "Quét Mã Nguồn (AST Scan)"}</span>
                </button>

                {scanResult && (
                  <span className="text-[11px] font-mono text-zinc-400">
                    Phát hiện: <strong className="text-zinc-200">{scanResult.routes.length}</strong> routes, <strong className="text-zinc-200">{scanResult.forms.length}</strong> forms
                  </span>
                )}
              </div>

              {/* Scanned Details */}
              {scanResult && (
                <div className="space-y-3 pt-3 border-t border-zinc-800">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
                    <span className="text-zinc-400">Frameworks:</span>
                    {scanResult.detected_frameworks.map((fw) => (
                      <span key={fw} className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800/60 text-[10px]">
                        {fw}
                      </span>
                    ))}
                    {scanResult.start_command && (
                      <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700 text-[10px]">
                        Cmd: {scanResult.start_command}
                      </span>
                    )}
                  </div>

                  {/* Discovered routes list */}
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-mono text-zinc-400 font-semibold">Routes đã phát hiện:</div>
                    <div className="max-h-40 overflow-y-auto space-y-1 font-mono text-[11px]">
                      {scanResult.routes.map((r, i) => (
                        <div key={i} className="flex items-center justify-between p-1.5 rounded bg-[#0a0a0c] border border-zinc-800/80">
                          <span className="text-zinc-200">{r.path}</span>
                          <span className="text-[10px] text-zinc-500">{r.type}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Card 2: Mode B Autonomous Dev Server Controller */}
            <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <Server className="h-4 w-4 text-purple-400" />
                  <span>Mode B: Dev Server Manager</span>
                </h3>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-mono text-[10px] ${
                  devServer?.is_running
                    ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/60"
                    : "bg-zinc-800 text-zinc-400"
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${devServer?.is_running ? "bg-emerald-400 animate-pulse" : "bg-zinc-500"}`}></span>
                  <span>{devServer?.is_running ? "Đang chạy" : "Đã dừng"}</span>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">Start Command:</label>
                  <input
                    type="text"
                    value={customCommand}
                    onChange={(e) => setCustomCommand(e.target.value)}
                    placeholder="e.g. npm run dev"
                    className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">Target Port (Optional):</label>
                  <input
                    type="text"
                    value={customPort}
                    onChange={(e) => setCustomPort(e.target.value)}
                    placeholder="e.g. 3000"
                    className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              {serverError && (
                <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-2.5 text-xs font-mono text-rose-300 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                  <span>{serverError}</span>
                </div>
              )}

              {devServer?.is_running && devServer.target_url && (
                <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-900/40 text-xs font-mono flex items-center justify-between">
                  <span className="text-zinc-400">Target URL: <strong className="text-emerald-400">{devServer.target_url}</strong></span>
                  <span className="text-[10px] text-zinc-500">PID: {devServer.pid} | Port: {devServer.port}</span>
                </div>
              )}

              <div className="flex items-center gap-2 pt-2 border-t border-zinc-800">
                {!devServer?.is_running ? (
                  <button
                    onClick={handleStartDevServer}
                    disabled={startingServer || !project.source_code_path}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-medium transition disabled:opacity-50 shadow-sm"
                  >
                    {startingServer ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <PlaySquare className="h-3.5 w-3.5" />
                    )}
                    <span>{startingServer ? "Đang khởi động..." : "Start Dev Server"}</span>
                  </button>
                ) : (
                  <button
                    onClick={handleStopDevServer}
                    disabled={stoppingServer}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-mono text-xs font-medium transition disabled:opacity-50 shadow-sm"
                  >
                    <Square className="h-3.5 w-3.5" />
                    <span>{stoppingServer ? "Đang dừng..." : "Stop Dev Server"}</span>
                  </button>
                )}
              </div>

              {/* Dev Server Log Terminal */}
              <div className="rounded-lg border border-zinc-800 bg-[#0a0a0c] overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900/60 border-b border-zinc-800 text-[10px] font-mono text-zinc-400">
                  <Terminal className="h-3 w-3 text-purple-400" />
                  <span>Dev Server Output Terminal</span>
                </div>
                <div className="p-2.5 font-mono text-[11px] text-zinc-400 max-h-32 overflow-y-auto whitespace-pre-wrap">
                  {devServer?.last_log || "Chưa có log từ tiến trình server..."}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Auto-Discovery & Crawler */}
      {activeTab === "discovery" && (
        <div className="space-y-6">
          {/* Action & Trigger Card */}
          <div className="rounded-xl border border-purple-500/30 bg-gradient-to-b from-purple-950/20 via-[#0f0f12] to-[#0f0f12] p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                  <Compass className="h-5 w-5 text-purple-400" />
                  <span>Autonomous Web Crawler & Discovery</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono border border-purple-500/30">
                    Tự động hoá
                  </span>
                </h3>
                <p className="text-xs text-zinc-400 max-w-2xl">
                  Playwright sẽ tự động &quot;bò&quot; khắp website {project.base_url}, quét mọi liên kết, tìm các form đăng nhập, form tìm kiếm, phát hiện link chết (404/500) và tự động tạo kịch bản kiểm thử.
                </p>
              </div>

              <button
                type="button"
                disabled={crawling}
                onClick={handleStartDiscovery}
                className="px-4 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center gap-2 transition disabled:opacity-50 shadow-md shrink-0"
              >
                <RefreshCw className={`h-4 w-4 ${crawling ? "animate-spin" : ""}`} />
                <span>{crawling ? "Đang quét toàn trang..." : "Bắt đầu khám phá (Start Crawl)"}</span>
              </button>
            </div>

            {crawlError && (
              <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-3 text-xs font-mono text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{crawlError}</span>
              </div>
            )}

            {saveSuccessMsg && (
              <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3 text-xs font-mono text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                <span>{saveSuccessMsg}</span>
              </div>
            )}

            {crawling && (
              <div className="rounded-lg border border-purple-500/40 bg-purple-950/30 p-4 text-xs font-mono text-purple-200 flex items-center gap-3 animate-pulse">
                <RefreshCw className="h-5 w-5 animate-spin text-purple-400 shrink-0" />
                <div>
                  <div className="font-semibold">Đang khám phá website bằng Playwright...</div>
                  <div className="text-[11px] text-purple-300/80 mt-0.5">
                    Hệ thống đang mở trình duyệt ngầm, phân tích DOM, dò tìm form và kiểm tra HTTP status...
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Discovery Metrics & Results */}
          {discoveryReport ? (
            <div className="space-y-6">
              {/* Stat Cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                      Trang đã khám phá
                    </div>
                    <div className="text-xl font-bold font-mono text-zinc-100">
                      {discoveryReport.pages_count}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
                    <Bug className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                      Liên kết chết (404/500)
                    </div>
                    <div className="text-xl font-bold font-mono text-rose-400">
                      {discoveryReport.broken_links_count}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    <Layers className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                      Forms & Tương tác
                    </div>
                    <div className="text-xl font-bold font-mono text-emerald-400">
                      {discoveryReport.forms_count}
                    </div>
                  </div>
                </div>
              </div>

              {/* Suggested Test Cases Section */}
              {discoveryReport.suggested_tests_json && discoveryReport.suggested_tests_json.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-purple-400" />
                        <span>Kịch bản kiểm thử tự động sinh (AI / Smart Discovery)</span>
                      </h4>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Hệ thống đã phân tích cây DOM và sinh ra các kịch bản kiểm thử sẵn sàng chạy. Bạn có thể thêm vào dự án với 1 cú click.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {discoveryReport.suggested_tests_json.map((st, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-zinc-800/80 bg-[#121216] p-4 flex flex-col justify-between gap-4 hover:border-purple-500/40 transition"
                      >
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <span className="font-mono text-sm font-semibold text-zinc-200">
                              {st.name}
                            </span>
                            <span className="shrink-0 text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/50">
                              {st.steps.length} actions
                            </span>
                          </div>
                          {st.description && (
                            <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                              {st.description}
                            </p>
                          )}

                          <div className="pt-2">
                            <div className="text-[11px] font-mono text-zinc-500 mb-1">Chuỗi hành động mô phỏng:</div>
                            <div className="flex flex-wrap gap-1 font-mono text-[10px]">
                              {st.steps.slice(0, 5).map((step, sIdx) => (
                                <span
                                  key={sIdx}
                                  className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50"
                                >
                                  {step.action} {step.url || step.selector?.split(",")[0] || ""}
                                </span>
                              ))}
                              {st.steps.length > 5 && (
                                <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                                  +{st.steps.length - 5} nữa
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="pt-3 border-t border-zinc-800/80 flex justify-end">
                          <button
                            type="button"
                            disabled={savingTestIdx === idx}
                            onClick={() => handleSaveDiscoveredTest(st, idx)}
                            className="px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/40 text-xs font-mono font-medium flex items-center gap-1.5 transition disabled:opacity-50"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            <span>{savingTestIdx === idx ? "Đang thêm..." : "Thêm vào Test Cases"}</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pages Crawled Table */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-zinc-400" />
                  <span>Danh sách các trang đã &quot;bò&quot; và kiểm tra ({discoveryReport.pages_count})</span>
                </h4>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-400 bg-[#141418]">
                        <th className="py-2.5 px-4 font-medium">Đường dẫn (Path)</th>
                        <th className="py-2.5 px-4 font-medium">Tiêu đề (Title)</th>
                        <th className="py-2.5 px-4 font-medium">HTTP Status</th>
                        <th className="py-2.5 px-4 font-medium">Forms</th>
                        <th className="py-2.5 px-4 font-medium">Links</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                      {(discoveryReport.pages_json || []).map((page, idx) => (
                        <tr key={idx} className="hover:bg-zinc-800/20">
                          <td className="py-2.5 px-4 font-semibold text-zinc-300">
                            {page.path}
                          </td>
                          <td className="py-2.5 px-4 text-zinc-400 max-w-xs truncate font-sans">
                            {page.title}
                          </td>
                          <td className="py-2.5 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                page.status_code >= 200 && page.status_code < 300
                                  ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/60"
                                  : "bg-rose-950/60 text-rose-400 border border-rose-800/60"
                              }`}
                            >
                              {page.status_code}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-zinc-400">
                            {page.forms_count}
                          </td>
                          <td className="py-2.5 px-4 text-zinc-400">
                            {page.links_found}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800/80 bg-[#0c0c0e] p-8 text-center space-y-3">
              <Compass className="h-8 w-8 text-zinc-600 mx-auto" />
              <div className="text-sm font-medium text-zinc-300">
                Chưa có báo cáo khám phá website
              </div>
              <p className="text-xs text-zinc-500 max-w-md mx-auto">
                Nhấn nút &quot;Bắt đầu khám phá (Start Crawl)&quot; bên trên để hệ thống tự động quét trang web và sinh các kịch bản kiểm thử.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

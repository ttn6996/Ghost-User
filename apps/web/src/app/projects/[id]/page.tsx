"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Project, TestCase, DiscoveryReport, StepAction } from "@/lib/types";
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

  // Tabs
  const [activeTab, setActiveTab] = useState<"tests" | "discovery">("tests");

  // Discovery state
  const [discoveryReport, setDiscoveryReport] = useState<DiscoveryReport | null>(null);
  const [crawling, setCrawling] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);
  const [savingTestIdx, setSavingTestIdx] = useState<number | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [projData, tcData, latestDiscovery] = await Promise.all([
        api.getProject(projectId),
        api.getTestCases(projectId),
        api.getLatestDiscovery(projectId).catch(() => null),
      ]);
      setProject(projData);
      setTestCases(tcData);
      if (latestDiscovery) {
        setDiscoveryReport(latestDiscovery);
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
      setSaveSuccessMsg(`Đã thêm thành công kịch bản "${created.name}" vào dự án! Bạn có thể chuyển sang tab Test Cases để chạy ngay.`);
    } catch (err: any) {
      alert(`Không thể lưu kịch bản: ${err.message}`);
    } finally {
      setSavingTestIdx(null);
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

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                setActiveTab("discovery");
                if (!discoveryReport && !crawling) {
                  handleStartDiscovery();
                }
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-purple-300 border border-purple-500/30 transition-colors shadow-sm"
            >
              <Compass className="h-4 w-4 text-purple-400" />
              <span>Khám phá tự động (Crawl)</span>
            </button>

            <Link
              href={`/tests/new?project_id=${project.id}`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              <span>Create Test Case</span>
            </Link>
          </div>
        </div>

        {project.description && (
          <p className="text-xs text-zinc-400 max-w-2xl">{project.description}</p>
        )}

        <div className="pt-4 border-t border-zinc-800/80 flex items-center gap-6 text-xs font-mono text-zinc-400">
          <div>
            Total Tests: <span className="text-zinc-200 font-semibold">{testCases.length}</span>
          </div>
          <div>
            Discovered Pages: <span className="text-zinc-200 font-semibold">{discoveryReport?.pages_count ?? 0}</span>
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
              description="Bạn có thể tạo kịch bản mới hoặc sử dụng tính năng Auto-Discovery để hệ thống tự động quét và sinh kịch bản."
              actionLabel="Tạo Test Case mới"
              onAction={() => router.push(`/tests/new?project_id=${project.id}`)}
            />
          )}
        </div>
      )}

      {/* TAB 2: Auto-Discovery & Crawler */}
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
                  Playwright sẽ tự động "bò" khắp website {project.base_url}, quét mọi liên kết, tìm các form đăng nhập, form tìm kiếm, phát hiện link chết (404/500) và tự động tạo kịch bản kiểm thử.
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
              {/* Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 font-mono">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-purple-400" />
                    <span>Trang phát hiện</span>
                  </div>
                  <div className="text-2xl font-bold text-zinc-100 mt-1">
                    {discoveryReport.pages_count}
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 font-mono">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5 text-blue-400" />
                    <span>Form tương tác</span>
                  </div>
                  <div className="text-2xl font-bold text-zinc-100 mt-1">
                    {discoveryReport.forms_count}
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 font-mono">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1.5">
                    <Bug className="h-3.5 w-3.5 text-rose-400" />
                    <span>Link hỏng (404/500)</span>
                  </div>
                  <div className="text-2xl font-bold text-zinc-100 mt-1">
                    {discoveryReport.broken_links_count}
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 font-mono">
                  <div className="text-[11px] text-zinc-400 flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Kịch bản tự tạo</span>
                  </div>
                  <div className="text-2xl font-bold text-zinc-100 mt-1">
                    {discoveryReport.suggested_tests_json?.length || 0}
                  </div>
                </div>
              </div>

              {/* Section 1: Auto-Generated Test Cases */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2 font-mono">
                  <Sparkles className="h-4 w-4 text-purple-400" />
                  <span>Kịch bản kiểm thử tự động tạo sẵn (Auto-Generated Test Cases)</span>
                </h3>

                {discoveryReport.suggested_tests_json && discoveryReport.suggested_tests_json.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {discoveryReport.suggested_tests_json.map((st, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-4 flex flex-col justify-between gap-3 hover:border-purple-500/40 transition-colors"
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-xs text-zinc-100 font-mono">
                              {st.name}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">
                              {st.steps.length} actions
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400 line-clamp-2">
                            {st.description || "Tự động tạo dựa trên kết quả quét website."}
                          </p>
                        </div>

                        <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between gap-2">
                          <span className="text-[10px] font-mono text-zinc-500">
                            {st.steps.map((s) => s.action).slice(0, 3).join(" ➔ ")}...
                          </span>
                          <button
                            type="button"
                            disabled={savingTestIdx === idx}
                            onClick={() => handleSaveDiscoveredTest(st, idx)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 border border-purple-500/40 text-xs font-mono transition-colors disabled:opacity-50 shrink-0"
                          >
                            <Plus className="h-3 w-3" />
                            <span>{savingTestIdx === idx ? "Đang thêm..." : "+ Thêm vào dự án"}</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center text-xs font-mono text-zinc-500 border border-zinc-800 rounded-xl bg-[#0f0f12]">
                    Chưa có kịch bản nào được sinh. Bấm "Bắt đầu khám phá" để quét website.
                  </div>
                )}
              </div>

              {/* Section 2: Discovered Pages Table */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2 font-mono">
                  <Layers className="h-4 w-4 text-zinc-400" />
                  <span>Sơ đồ các trang web phát hiện (Discovered Pages & Sitemaps)</span>
                </h3>

                {discoveryReport.pages_json && discoveryReport.pages_json.length > 0 ? (
                  <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-zinc-800 text-zinc-400 font-mono bg-[#141418]">
                          <th className="py-2.5 px-4 font-medium">Đường dẫn (Path)</th>
                          <th className="py-2.5 px-4 font-medium">Tiêu đề (Title)</th>
                          <th className="py-2.5 px-4 font-medium">Trạng thái (HTTP)</th>
                          <th className="py-2.5 px-4 font-medium">Form</th>
                          <th className="py-2.5 px-4 font-medium text-right">Liên kết</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800 font-mono">
                        {discoveryReport.pages_json.map((page, idx) => (
                          <tr key={idx} className="hover:bg-zinc-800/20">
                            <td className="py-2.5 px-4 font-semibold text-zinc-200">
                              <a
                                href={page.url}
                                target="_blank"
                                rel="noreferrer"
                                className="hover:text-purple-400 hover:underline flex items-center gap-1"
                              >
                                <span>{page.path}</span>
                                <ExternalLink className="h-2.5 w-2.5 text-zinc-500" />
                              </a>
                            </td>
                            <td className="py-2.5 px-4 text-zinc-300 font-sans truncate max-w-xs">
                              {page.title || "—"}
                            </td>
                            <td className="py-2.5 px-4">
                              <span
                                className={`inline-flex px-2 py-0.5 rounded text-[10px] ${
                                  page.status_code >= 200 && page.status_code < 400
                                    ? "bg-emerald-950/40 text-emerald-400 border border-emerald-800/40"
                                    : "bg-rose-950/40 text-rose-400 border border-rose-800/40"
                                }`}
                              >
                                {page.status_code} {page.status_code === 200 ? "OK" : page.status_code === 404 ? "Not Found" : ""}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-zinc-400">
                              {page.forms_count > 0 ? (
                                <span className="text-purple-300 font-semibold">{page.forms_count} form</span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td className="py-2.5 px-4 text-right text-zinc-400">
                              {page.links_found} links
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-6 text-center text-xs font-mono text-zinc-500 border border-zinc-800 rounded-xl bg-[#0f0f12]">
                    Chưa có trang nào được phát hiện.
                  </div>
                )}
              </div>
            </div>
          ) : (
            !crawling && (
              <EmptyState
                icon={Compass}
                title="Chưa thực hiện quét tự động"
                description="Bấm 'Bắt đầu khám phá' để Playwright tự động quét cấu trúc website, nhận diện form và tạo sẵn các test case mẫu."
                actionLabel="Bắt đầu khám phá (Start Crawl)"
                onAction={handleStartDiscovery}
              />
            )
          )}
        </div>
      )}
    </div>
  );
}

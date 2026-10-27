"use client";

import React, { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Project, StepAction } from "@/lib/types";
import { StepEditor } from "@/components/step-editor/StepEditor";
import { 
  ArrowLeft, 
  Save, 
  CheckCircle2, 
  AlertCircle, 
  Sparkles 
} from "lucide-react";

function NewTestContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("project_id") || "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);

  const [steps, setSteps] = useState<StepAction[]>([
    { action: "goto", url: "/" },
    { action: "assert_visible", selector: "h1" },
  ]);

  const [validationState, setValidationState] = useState<{
    tested: boolean;
    valid: boolean;
    errors: string[];
  }>({ tested: false, valid: false, errors: [] });

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // AI Prompt State
  const [aiPrompt, setAiPrompt] = useState("");
  const [generatingAi, setGeneratingAi] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSuccessMessage, setAiSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    api.getProjects().then((projs) => {
      setProjects(projs);
      if (!selectedProjectId && projs.length > 0) {
        setSelectedProjectId(projs[0].id);
      }
    });
  }, []);

  const handleValidate = async () => {
    try {
      const def = { name: name || "Test Journey", steps };
      const res = await api.validateTestDefinition(def);
      setValidationState({ tested: true, valid: res.valid, errors: res.errors });
    } catch (err: any) {
      setValidationState({ tested: true, valid: false, errors: [err.message] });
    }
  };

  const loadTemplate = (type: "search" | "login") => {
    if (type === "search") {
      setName("Product Search Journey");
      setDescription("Searches for a keyword and verifies results list");
      setSteps([
        { action: "goto", url: "/" },
        { action: "fill", selector: "input[name='q']", value: "laptop" },
        { action: "click", selector: "button[type='submit']" },
        { action: "wait_for_visible", selector: "[data-testid='search-results']" },
        { action: "assert_visible", selector: "[data-testid='search-results']" },
        { action: "screenshot", name: "search_results" },
      ]);
    } else {
      setName("Authentication Journey");
      setDescription("Fills user login credentials and checks dashboard access");
      setSteps([
        { action: "goto", url: "/login" },
        { action: "fill", selector: "input#email", value: "user@example.com" },
        { action: "fill", selector: "input#password", value: "Secr3tPassword!" },
        { action: "click", selector: "button#submit" },
        { action: "assert_url", expected_url: "/dashboard" },
        { action: "assert_visible", selector: "#welcome-banner" },
        { action: "screenshot", name: "dashboard_loaded" },
      ]);
    }
  };

  const handleGenerateAi = async (customPrompt?: string) => {
    const textToUse = customPrompt || aiPrompt;
    if (!selectedProjectId) {
      setAiError("Vui lòng chọn Target Project trước khi tạo kịch bản");
      return;
    }
    if (!textToUse.trim()) {
      setAiError("Vui lòng nhập câu lệnh mô tả kịch bản bạn muốn test");
      return;
    }

    try {
      setGeneratingAi(true);
      setAiError(null);
      setAiSuccessMessage(null);

      const res = await api.generateTestCase({
        project_id: selectedProjectId,
        prompt: textToUse.trim(),
      });

      setName(res.suggested_name);
      if (res.suggested_description) {
        setDescription(res.suggested_description);
      }
      setSteps(res.steps);
      setAiSuccessMessage(`✨ Đã tự động tạo ${res.steps.length} bước kiểm thử thành công bằng ${res.model_used}!`);
    } catch (err: any) {
      setAiError(err.message || "Tự động sinh kịch bản thất bại.");
    } finally {
      setGeneratingAi(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProjectId) {
      setSubmitError("Please select a target project");
      return;
    }
    if (!name.trim()) {
      setSubmitError("Please provide a test name");
      return;
    }

    try {
      setSubmitting(true);
      setSubmitError(null);

      const payload = {
        project_id: selectedProjectId,
        name,
        description: description || undefined,
        enabled,
        definition_json: {
          name,
          description: description || undefined,
          steps,
        },
      };

      const created = await api.createTestCase(payload);
      router.push(`/projects/${selectedProjectId}`);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to create test case");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link
          href="/tests"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Test Cases</span>
        </Link>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Create Test Case</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Define a browser automation sequence with strict step validations.
          </p>
        </div>

        {/* Templates */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-zinc-400">Templates:</span>
          <button
            type="button"
            onClick={() => loadTemplate("search")}
            className="px-2.5 py-1 text-xs rounded border border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 flex items-center gap-1 font-mono"
          >
            <Sparkles className="h-3 w-3 text-purple-400" />
            <span>Search</span>
          </button>
          <button
            type="button"
            onClick={() => loadTemplate("login")}
            className="px-2.5 py-1 text-xs rounded border border-zinc-800 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 flex items-center gap-1 font-mono"
          >
            <Sparkles className="h-3 w-3 text-purple-400" />
            <span>Login</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {submitError && (
          <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4 text-xs font-mono text-rose-300 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{submitError}</span>
          </div>
        )}

        {/* Metadata Card */}
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Target Project *
              </label>
              <select
                required
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs font-mono text-zinc-200 focus:border-purple-500 focus:outline-none"
              >
                <option value="">-- Choose Project --</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.base_url})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Test Case Name *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. User Registration Journey"
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">
              Description (Optional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this journey verifies..."
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled-check"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-900 text-purple-600 focus:ring-0"
            />
            <label htmlFor="enabled-check" className="text-xs text-zinc-300 font-mono">
              Enabled (active for execution and scheduling)
            </label>
          </div>
        </div>

        {/* AI Prompt-to-Journey Card */}
        <div className="rounded-xl border border-purple-500/30 bg-gradient-to-b from-purple-950/20 via-[#0f0f12] to-[#0f0f12] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-300">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  <span>AI Prompt-to-Journey</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono border border-purple-500/30">
                    Tự động hoá
                  </span>
                </h3>
                <p className="text-[11px] text-zinc-400">
                  Nhập câu lệnh bằng tiếng Việt hoặc tiếng Anh — hệ thống sẽ tự động phân tích và tạo kịch bản cho bạn mà không cần nhớ selector.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-2 pt-1">
            <div className="relative">
              <textarea
                rows={3}
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Ví dụ: 'Vào trang login, đăng nhập bằng tài khoản user01 và mật khẩu admin123, sau đó kiểm tra xem đã vào được trang chủ chưa và chụp ảnh'"
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] p-3 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-purple-500 focus:outline-none"
              />
            </div>

            {/* Quick Chips */}
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[10px] font-mono text-zinc-500">Gợi ý mẫu:</span>
              {[
                { label: "🔑 Đăng nhập user01 / admin123", text: "Vào trang login, đăng nhập bằng tài khoản user01 và mật khẩu admin123, sau đó kiểm tra đã vào được trang chủ chưa" },
                { label: "❌ Thử đăng nhập sai mật khẩu", text: "Đăng nhập với user01 và mật khẩu sai abc để kiểm tra thông báo lỗi hiển thị" },
                { label: "🔍 Tìm kiếm sản phẩm giáo trình", text: "Vào chợ marketplace, tìm kiếm sản phẩm giáo trình và chụp ảnh kết quả" },
                { label: "📖 Xem hướng dẫn & mở FAQ", text: "Vào trang /about-guide, kiểm tra tiêu đề và mở FAQ giải đáp" },
                { label: "📝 Điền form đăng ký", text: "Vào trang /register, điền form đăng ký với họ tên Nguyễn Văn A, email test@example.com và mật khẩu Pass@123" },
              ].map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setAiPrompt(chip.text);
                    handleGenerateAi(chip.text);
                  }}
                  className="px-2 py-0.5 text-[11px] rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-purple-300 transition-colors"
                >
                  {chip.label}
                </button>
              ))}
            </div>

            <div className="flex items-center justify-between pt-1">
              <div className="flex-1">
                {aiError && (
                  <p className="text-xs text-rose-400 flex items-center gap-1.5 font-mono">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{aiError}</span>
                  </p>
                )}
                {aiSuccessMessage && (
                  <p className="text-xs text-emerald-400 flex items-center gap-1.5 font-mono">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    <span>{aiSuccessMessage}</span>
                  </p>
                )}
              </div>

              <button
                type="button"
                disabled={generatingAi}
                onClick={() => handleGenerateAi()}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-purple-600 hover:bg-purple-500 text-white flex items-center gap-2 transition disabled:opacity-50 shadow-sm shrink-0"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>{generatingAi ? "Đang phân tích & tạo..." : "Tự động tạo kịch bản"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Step Editor Card */}
        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5">
          <StepEditor steps={steps} onChange={setSteps} />
        </div>

        {/* Validation Result Banner */}
        {validationState.tested && (
          <div
            className={`rounded-xl border p-4 text-xs font-mono flex items-start gap-2.5 ${
              validationState.valid
                ? "border-emerald-900/60 bg-emerald-950/20 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/20 text-rose-300"
            }`}
          >
            {validationState.valid ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
            )}
            <div>
              <div className="font-semibold">
                {validationState.valid
                  ? "Schema Validation Passed: Definition structure is clean and ready."
                  : "Schema Validation Failed:"}
              </div>
              {validationState.errors.map((err, i) => (
                <div key={i} className="mt-1">
                  - {err}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleValidate}
            className="px-4 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-xs font-medium text-zinc-200 hover:bg-zinc-700 transition-colors"
          >
            Validate Steps Schema
          </button>

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            <span>{submitting ? "Saving..." : "Save Test Case"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}

export default function NewTestPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs font-mono text-zinc-400">Loading form...</div>}>
      <NewTestContent />
    </Suspense>
  );
}

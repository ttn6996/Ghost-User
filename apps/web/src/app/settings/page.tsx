"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AISetting, AITestConnectionResult } from "@/lib/types";
import { 
  Settings as SettingsIcon, 
  ShieldCheck, 
  Database, 
  Cpu, 
  HardDrive, 
  Activity, 
  CheckCircle2, 
  AlertTriangle,
  Sparkles,
  Bot,
  RefreshCw,
  Eye,
  EyeOff,
  Save,
  Server,
  Key,
  Globe,
  Loader2
} from "lucide-react";

const PROVIDER_PRESETS: Record<string, { name: string; defaultUrl: string; defaultModel: string; hint: string }> = {
  gemini: {
    name: "Google Gemini",
    defaultUrl: "https://generativelanguage.googleapis.com",
    defaultModel: "gemini-1.5-flash",
    hint: "Miễn phí mức cơ bản, hỗ trợ multimodal vision đọc screenshot Playwright cực nhanh.",
  },
  openai: {
    name: "OpenAI (GPT-4o)",
    defaultUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o-mini",
    hint: "Hỗ trợ GPT-4o, GPT-4o-mini, phù hợp tư duy logic nghiệp vụ test phức tạp.",
  },
  anthropic: {
    name: "Anthropic Claude",
    defaultUrl: "https://api.anthropic.com/v1",
    defaultModel: "claude-3-5-sonnet-20241022",
    hint: "Claude 3.5 Sonnet với khả năng phân tích UI/UX và logic xuất sắc.",
  },
  custom_openai: {
    name: "Custom / Local (Ollama, LM Studio, OpenRouter, Groq, DeepSeek)",
    defaultUrl: "http://localhost:11434/v1",
    defaultModel: "llama3.2",
    hint: "Tương thích chuẩn OpenAI API. Dùng Ollama local (offline 100%) hoặc OpenRouter, Groq, DeepSeek.",
  },
};

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AI Configuration State
  const [aiProvider, setAiProvider] = useState("gemini");
  const [aiBaseUrl, setAiBaseUrl] = useState(PROVIDER_PRESETS.gemini.defaultUrl);
  const [aiApiKey, setAiApiKey] = useState("");
  const [maskedKeyFromDb, setMaskedKeyFromDb] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [aiModel, setAiModel] = useState(PROVIDER_PRESETS.gemini.defaultModel);
  const [aiEnabled, setAiEnabled] = useState(true);

  // Dynamic Models State
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadModelsMsg, setLoadModelsMsg] = useState<string | null>(null);

  // AI Connection Test State
  const [testingAI, setTestingAI] = useState(false);
  const [aiTestResult, setAiTestResult] = useState<AITestConnectionResult | null>(null);

  // Save State
  const [savingAI, setSavingAI] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const testConnection = async () => {
    try {
      setTesting(true);
      setError(null);
      const start = performance.now();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/health`, { cache: "no-store" });
      const elapsed = Math.round(performance.now() - start);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHealth(data);
      setLatency(elapsed);
    } catch (err: any) {
      setError(err.message || "Failed to reach Ghost-User API");
      setHealth(null);
      setLatency(null);
    } finally {
      setTesting(false);
    }
  };

  const loadCurrentAISettings = async () => {
    try {
      const setting = await api.getAISettings();
      if (setting) {
        setAiProvider(setting.provider || "gemini");
        setAiBaseUrl(setting.base_url || PROVIDER_PRESETS[setting.provider]?.defaultUrl || "");
        setAiModel(setting.model || "gemini-1.5-flash");
        setAiEnabled(setting.enabled ?? true);
        if (setting.api_key_masked) {
          setMaskedKeyFromDb(setting.api_key_masked);
        }
      }
    } catch (err) {
      console.error("Could not load AI settings:", err);
    }
  };

  useEffect(() => {
    testConnection();
    loadCurrentAISettings();
  }, []);

  const handleProviderChange = (newProvider: string) => {
    setAiProvider(newProvider);
    const preset = PROVIDER_PRESETS[newProvider];
    if (preset) {
      setAiBaseUrl(preset.defaultUrl);
      setAiModel(preset.defaultModel);
    }
    setAvailableModels([]);
    setAiTestResult(null);
  };

  const handleLoadModels = async () => {
    try {
      setLoadingModels(true);
      setLoadModelsMsg(null);
      const res = await api.loadAIModels({
        provider: aiProvider,
        base_url: aiBaseUrl || undefined,
        api_key: aiApiKey || undefined,
      });
      setAvailableModels(res.models || []);
      setLoadModelsMsg(`Đã tải thành công ${res.models.length} model khả dụng từ provider!`);
      if (res.models.length > 0 && !res.models.includes(aiModel)) {
        setAiModel(res.models[0]);
      }
    } catch (err: any) {
      setLoadModelsMsg(`Không thể tải models: ${err.message}`);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleTestAIConnection = async () => {
    try {
      setTestingAI(true);
      setAiTestResult(null);
      const res = await api.testAIConnection({
        provider: aiProvider,
        base_url: aiBaseUrl || undefined,
        api_key: aiApiKey || undefined,
        model: aiModel || undefined,
      });
      setAiTestResult(res);
    } catch (err: any) {
      setAiTestResult({
        success: false,
        provider: aiProvider,
        base_url: aiBaseUrl,
        model: aiModel,
        latency_ms: 0,
        error: err.message || "Failed to reach AI provider",
      });
    } finally {
      setTestingAI(false);
    }
  };

  const handleSaveAISettings = async () => {
    try {
      setSavingAI(true);
      setSaveSuccess(false);
      const saved = await api.saveAISettings({
        provider: aiProvider,
        base_url: aiBaseUrl || undefined,
        api_key: aiApiKey || undefined,
        model: aiModel,
        enabled: aiEnabled,
      });
      if (saved.api_key_masked) {
        setMaskedKeyFromDb(saved.api_key_masked);
      }
      setAiApiKey("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } catch (err: any) {
      alert(`Lưu cấu hình AI thất bại: ${err.message}`);
    } finally {
      setSavingAI(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">System Settings & Status</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Cấu hình môi trường, trí tuệ nhân tạo (Multi-AI Providers), kết nối backend engine và bảo mật SSRF.
        </p>
      </div>

      {/* AI Model & Multi-Provider Configuration Card */}
      <div className="rounded-xl border border-purple-500/40 bg-gradient-to-b from-purple-950/20 via-[#0f0f12] to-[#0f0f12] p-6 space-y-6 shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-sm">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-zinc-100">AI Intelligence & Multi-Model Engine</h2>
                <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono text-[10px] border border-purple-500/30">
                  Universal AI
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Cho phép kết nối bất kỳ nhà cung cấp AI nào (Gemini, OpenAI, Claude, hoặc Ollama local) để tự động suy nghĩ kịch bản và phân tích ảnh chụp giao diện.
              </p>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer font-mono text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={aiEnabled}
              onChange={(e) => setAiEnabled(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-900 text-purple-600 focus:ring-0"
            />
            <span>Kích hoạt AI Engine</span>
          </label>
        </div>

        <div className="space-y-4 pt-2">
          {/* 1. Provider Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Nhà cung cấp AI (Provider) *
              </label>
              <select
                value={aiProvider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
              >
                {Object.entries(PROVIDER_PRESETS).map(([key, item]) => (
                  <option key={key} value={key}>
                    {item.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px] text-zinc-500">
                {PROVIDER_PRESETS[aiProvider]?.hint}
              </p>
            </div>

            {/* 2. Base URL */}
            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Base URL của AI Endpoint *
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={aiBaseUrl}
                  onChange={(e) => setAiBaseUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
                />
              </div>
              <p className="mt-1 text-[11px] text-zinc-500">
                Hỗ trợ bất kỳ endpoint proxy, Ollama URL (<code className="text-zinc-400">http://localhost:11434/v1</code>) hoặc OpenRouter.
              </p>
            </div>
          </div>

          {/* 3. API Key */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-mono text-zinc-300">
                API Key {aiProvider === "custom_openai" ? "(Tùy chọn nếu dùng Ollama local)" : "*"}
              </label>
              {maskedKeyFromDb && (
                <span className="text-[11px] font-mono text-zinc-500">
                  Đã lưu: <strong className="text-zinc-300">{maskedKeyFromDb}</strong>
                </span>
              )}
            </div>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={aiApiKey}
                onChange={(e) => setAiApiKey(e.target.value)}
                placeholder={maskedKeyFromDb ? "Nhập key mới nếu muốn thay đổi..." : "e.g. AIzaSy... hoặc sk-..."}
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 pr-10 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2.5 top-2.5 text-zinc-500 hover:text-zinc-300"
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* 4. Model Selection & Dynamic Model Discovery */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-mono text-zinc-300">
                  Model AI được chọn *
                </label>
                <button
                  type="button"
                  onClick={handleLoadModels}
                  disabled={loadingModels}
                  className="inline-flex items-center gap-1 text-[11px] font-mono text-purple-400 hover:text-purple-300 hover:underline disabled:opacity-50"
                >
                  <RefreshCw className={`h-3 w-3 ${loadingModels ? "animate-spin" : ""}`} />
                  <span>{loadingModels ? "Đang tải models..." : "Load Models từ API"}</span>
                </button>
              </div>

              {availableModels.length > 0 ? (
                <select
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  placeholder="e.g. gemini-1.5-flash or gpt-4o-mini"
                  className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
                />
              )}
              {loadModelsMsg && (
                <p className="mt-1 text-[11px] font-mono text-zinc-400">
                  {loadModelsMsg}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-mono text-zinc-300 mb-1">
                Nhập Model thủ công (Custom Model Override)
              </label>
              <input
                type="text"
                value={aiModel}
                onChange={(e) => setAiModel(e.target.value)}
                placeholder="Gõ tên model bất kỳ nếu không có trong list"
                className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 font-mono focus:border-purple-500 focus:outline-none"
              />
              <p className="mt-1 text-[11px] text-zinc-500">
                Hỗ trợ bất kỳ custom model tag nào (e.g. <code className="text-zinc-400">qwen2.5-coder:14b</code>).
              </p>
            </div>
          </div>

          {/* Test Result Display */}
          {aiTestResult && (
            <div
              className={`p-3 rounded-lg border text-xs font-mono flex items-start gap-2.5 ${
                aiTestResult.success
                  ? "border-emerald-900/60 bg-emerald-950/20 text-emerald-300"
                  : "border-rose-900/60 bg-rose-950/20 text-rose-300"
              }`}
            >
              {aiTestResult.success ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">
                    {aiTestResult.success ? "Kết nối AI thành công!" : "Kiểm tra kết nối thất bại"}
                  </span>
                  <span className="text-[10px] text-zinc-400">
                    Độ trễ: {aiTestResult.latency_ms}ms
                  </span>
                </div>
                {aiTestResult.reply && (
                  <div className="text-[11px] text-emerald-400/90">
                    Phản hồi từ {aiTestResult.model}: &quot;{aiTestResult.reply}&quot;
                  </div>
                )}
                {aiTestResult.error && (
                  <div className="text-[11px] text-rose-300 whitespace-pre-wrap">
                    Chi tiết lỗi: {aiTestResult.error}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-800">
            <button
              type="button"
              onClick={handleTestAIConnection}
              disabled={testingAI}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-purple-500/40 bg-purple-950/30 hover:bg-purple-900/40 text-xs font-mono font-medium text-purple-300 transition disabled:opacity-50"
            >
              {testingAI ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              )}
              <span>{testingAI ? "Đang gửi ping test..." : "Test Connection (Kiểm tra Key & Model)"}</span>
            </button>

            <div className="flex items-center gap-3">
              {saveSuccess && (
                <span className="text-xs font-mono text-emerald-400 flex items-center gap-1 animate-fade-in">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Đã lưu thành công!</span>
                </span>
              )}
              <button
                type="button"
                onClick={handleSaveAISettings}
                disabled={savingAI}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white transition disabled:opacity-50 shadow-sm"
              >
                {savingAI ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                <span>{savingAI ? "Đang lưu..." : "Lưu Cấu Hình AI"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Backend API & Engine Card */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-zinc-100">API Service Connectivity</h2>
              <p className="text-xs text-zinc-400">FastAPI backend connection and database heartbeat</p>
            </div>
          </div>

          <button
            onClick={testConnection}
            disabled={testing}
            className="px-3.5 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800 text-xs font-mono text-zinc-200 hover:bg-zinc-700 transition-colors disabled:opacity-50"
          >
            {testing ? "Testing..." : "Test Connection"}
          </button>
        </div>

        {latency !== null && health && (
          <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-4 text-xs font-mono text-emerald-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span>Status: Operational ({health.service})</span>
            </div>
            <div className="text-zinc-400">
              Roundtrip: <span className="text-emerald-400 font-semibold">{latency}ms</span> | DB: <span className="text-emerald-400">{health.database}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-4 text-xs font-mono text-rose-300 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-400" />
            <span>Connection check failed: {error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 font-mono text-xs text-zinc-300">
          <div className="p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <span className="text-zinc-500 block text-[10px] uppercase mb-1">API Base URL</span>
            <span>{process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}</span>
          </div>
          <div className="p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <span className="text-zinc-500 block text-[10px] uppercase mb-1">Runtime Environment</span>
            <span>{health?.environment || "development"}</span>
          </div>
        </div>
      </div>

      {/* Security Policies Card */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Safe Execution & SSRF Guards</h2>
            <p className="text-xs text-zinc-400">Security boundaries enforced during Playwright automation</p>
          </div>
        </div>

        <div className="space-y-3 pt-2 font-mono text-xs">
          <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <div>
              <span className="font-semibold text-zinc-200">Private IP / RFC1918 Blocking</span>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                Blocks navigations resolving to 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, and cloud metadata (169.254.169.254).
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-950/40 border border-emerald-800/60 text-emerald-400">
              Enforced
            </span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <div>
              <span className="font-semibold text-zinc-200">Origin Domain Confinement</span>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                Journeys are strictly confined to the project&apos;s base URL origin.
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-950/40 border border-emerald-800/60 text-emerald-400">
              Enforced
            </span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <div>
              <span className="font-semibold text-zinc-200">Artifact Traversal Guard</span>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                Screenshots and traces are served strictly from validated subpaths.
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-950/40 border border-emerald-800/60 text-emerald-400">
              Enforced
            </span>
          </div>
        </div>
      </div>

      {/* Storage and Browser Configuration */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Browser & Storage Engine</h2>
            <p className="text-xs text-zinc-400">Automation runtime parameters and persistence configuration</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 font-mono text-xs">
          <div className="p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <span className="text-zinc-500 block text-[10px] uppercase mb-1">Browser Engine</span>
            <span className="text-zinc-200 font-semibold">Playwright Chromium</span>
          </div>
          <div className="p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <span className="text-zinc-500 block text-[10px] uppercase mb-1">Persistence</span>
            <span className="text-zinc-200 font-semibold">SQLite WAL Mode</span>
          </div>
          <div className="p-3 rounded-lg border border-zinc-800/80 bg-[#121216]">
            <span className="text-zinc-500 block text-[10px] uppercase mb-1">Trace Mode</span>
            <span className="text-zinc-200 font-semibold">Preserve on Failure</span>
          </div>
        </div>
      </div>
    </div>
  );
}

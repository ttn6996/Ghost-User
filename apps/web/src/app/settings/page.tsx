"use client";

import React, { useEffect, useState } from "react";
import { 
  Settings as SettingsIcon, 
  ShieldCheck, 
  Database, 
  Cpu, 
  HardDrive, 
  Activity, 
  CheckCircle2, 
  AlertTriangle 
} from "lucide-react";

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    testConnection();
  }, []);

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">System Settings & Status</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Environment configuration, backend engine connectivity, and runtime security policies.
        </p>
      </div>

      {/* Backend API & Engine Card */}
      <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
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
                Journeys are strictly confined to the project's base URL origin.
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

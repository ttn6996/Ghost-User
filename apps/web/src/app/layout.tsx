import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { 
  Bot, 
  FolderKanban, 
  PlayCircle, 
  History, 
  CalendarClock, 
  Settings, 
  Activity 
} from "lucide-react";

export const metadata: Metadata = {
  title: "Ghost-User | Autonomous Website Testing Agent",
  description: "Simulate user journeys, verify expected behavior, and capture test evidence reliably.",
};

const navItems = [
  { href: "/", label: "Overview", icon: Activity },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/tests", label: "Test Cases", icon: PlayCircle },
  { href: "/runs", label: "Run History", icon: History },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0c0d10] text-zinc-100 flex min-h-screen">
        {/* Sidebar */}
        <aside className="w-64 border-r border-[#20232d] bg-[#111318] flex flex-col shrink-0 select-none">
          <div className="h-16 flex items-center px-6 border-b border-[#20232d] gap-3">
            <div className="h-8 w-8 rounded-lg bg-zinc-900 border border-zinc-700/80 flex items-center justify-center text-zinc-100 shadow-sm">
              <Bot className="h-4.5 w-4.5 text-zinc-200" />
            </div>
            <div>
              <div className="font-semibold text-sm tracking-tight text-white flex items-center gap-1.5">
                <span>Ghost-User</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-zinc-800 border border-zinc-700/80 text-zinc-300 font-mono font-medium">v0.1</span>
              </div>
              <div className="text-[10px] text-zinc-400 tracking-wider font-mono uppercase">AUTONOMOUS QA</div>
            </div>
          </div>

          <div className="px-3 py-4 flex-1 space-y-1">
            <div className="px-3 pb-2 text-[10px] uppercase font-bold tracking-wider text-zinc-400">
              Workspace
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-100 hover:bg-[#181b23] transition-all"
                >
                  <Icon className="h-4 w-4 shrink-0 text-zinc-400" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>

          {/* System status pill in sidebar footer */}
          <div className="p-4 border-t border-[#20232d] bg-[#0d0f14]">
            <div className="flex items-center justify-between text-xs text-zinc-300 mb-1.5">
              <span className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="font-medium text-zinc-200">Engine Ready</span>
              </span>
              <span className="font-mono text-[10px] text-zinc-400">Playwright</span>
            </div>
            <div className="text-[11px] text-zinc-400 font-mono truncate">
              Local Worker Active
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 border-b border-[#20232d] bg-[#111318]/70 backdrop-blur-md px-8 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
              <span className="text-zinc-400">WORKSPACE</span>
              <span className="text-zinc-400">/</span>
              <span className="text-zinc-200 font-medium">default-env</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono bg-zinc-900 border border-zinc-800 text-zinc-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                Dev Environment
              </span>
            </div>
          </header>

          <main className="flex-1 p-8 overflow-y-auto bg-[#0c0d10]">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

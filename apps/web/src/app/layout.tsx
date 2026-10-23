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
      <body className="bg-dark-400 text-zinc-100 flex min-h-screen">
        {/* Sidebar */}
        <aside className="w-64 border-r border-zinc-800 bg-[#0e0e11] flex flex-col shrink-0">
          <div className="h-16 flex items-center px-6 border-b border-zinc-800 gap-3">
            <div className="h-8 w-8 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-sm">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="font-semibold text-sm tracking-tight text-zinc-100">Ghost-User</div>
              <div className="text-[11px] text-zinc-400 tracking-wide font-mono">AUTONOMOUS QA</div>
            </div>
          </div>

          <div className="px-3 py-4 flex-1 space-y-1">
            <div className="px-3 pb-2 text-[10px] uppercase font-bold tracking-wider text-zinc-400">
              Navigation
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 transition-colors"
                >
                  <Icon className="h-4 w-4 shrink-0 text-zinc-400" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>

          {/* System status pill in sidebar footer */}
          <div className="p-4 border-t border-zinc-800 bg-[#0c0c0e]">
            <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Engine Ready
              </span>
              <span className="font-mono text-[10px] text-zinc-400">v0.1.0</span>
            </div>
            <div className="text-[11px] text-zinc-400 font-mono truncate">
              Local Playwright Worker
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 border-b border-zinc-800 bg-[#0e0e11]/50 backdrop-blur px-8 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
              <span className="text-zinc-300">WORKSPACE</span>
              <span>/</span>
              <span className="text-purple-400 font-semibold">default-env</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-zinc-800 border border-zinc-700 text-zinc-300">
                Mode: Development
              </span>
            </div>
          </header>

          <main className="flex-1 p-8 overflow-y-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

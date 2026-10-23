import React from "react";
import { RunStatus, StepStatus } from "@/lib/types";
import { CheckCircle2, XCircle, AlertTriangle, Clock, PlayCircle, Ban } from "lucide-react";

interface StatusBadgeProps {
  status: RunStatus | StepStatus | string;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  const s = status.toLowerCase();

  const configs: Record<string, { label: string; bg: string; text: string; border: string; icon: any }> = {
    passed: {
      label: "Passed",
      bg: "bg-emerald-950/40",
      text: "text-emerald-400",
      border: "border-emerald-800/60",
      icon: CheckCircle2,
    },
    failed: {
      label: "Failed",
      bg: "bg-rose-950/40",
      text: "text-rose-400",
      border: "border-rose-800/60",
      icon: XCircle,
    },
    error: {
      label: "Error",
      bg: "bg-amber-950/40",
      text: "text-amber-400",
      border: "border-amber-800/60",
      icon: AlertTriangle,
    },
    running: {
      label: "Running",
      bg: "bg-purple-950/40",
      text: "text-purple-400",
      border: "border-purple-800/60",
      icon: PlayCircle,
    },
    queued: {
      label: "Queued",
      bg: "bg-zinc-900",
      text: "text-zinc-400",
      border: "border-zinc-700",
      icon: Clock,
    },
    cancelled: {
      label: "Cancelled",
      bg: "bg-zinc-900/60",
      text: "text-zinc-400",
      border: "border-zinc-800",
      icon: Ban,
    },
    skipped: {
      label: "Skipped",
      bg: "bg-zinc-900/40",
      text: "text-zinc-400",
      border: "border-zinc-800",
      icon: Clock,
    },
  };

  const config = configs[s] || {
    label: status,
    bg: "bg-zinc-900",
    text: "text-zinc-400",
    border: "border-zinc-800",
    icon: Clock,
  };

  const Icon = config.icon;
  const isSm = size === "sm";

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-md font-mono ${
        isSm ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs"
      } ${config.bg} ${config.text} ${config.border}`}
    >
      <Icon className={`${isSm ? "h-3 w-3" : "h-3.5 w-3.5"} shrink-0 ${s === "running" ? "animate-spin" : ""}`} />
      <span>{config.label}</span>
    </span>
  );
};

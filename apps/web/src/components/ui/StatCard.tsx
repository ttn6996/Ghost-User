import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
}) => {
  return (
    <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">{title}</span>
        <div className="h-8 w-8 rounded-lg bg-zinc-800/80 border border-zinc-700/60 flex items-center justify-center text-zinc-400">
          <Icon className="h-4 w-4 text-purple-400" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono tracking-tight text-zinc-100">{value}</span>
        {trend && (
          <span className="text-xs text-zinc-400 font-mono">
            {trend}
          </span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-xs text-zinc-400">{subtitle}</p>}
    </div>
  );
};

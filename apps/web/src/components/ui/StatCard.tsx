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
    <div className="relative rounded-xl border border-[#232630] bg-[#13151b] p-5 shadow-subtle hover:border-[#2f3442] transition-colors overflow-hidden group">
      {/* Top subtle highlight */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
      
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">{title}</span>
        <div className="h-8 w-8 rounded-lg bg-zinc-900/90 border border-zinc-800/80 flex items-center justify-center text-zinc-400 group-hover:text-zinc-200 group-hover:border-zinc-700/80 transition-colors">
          <Icon className="h-4 w-4" />
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
      {subtitle && <p className="mt-1 text-xs text-zinc-400 leading-normal">{subtitle}</p>}
    </div>
  );
};

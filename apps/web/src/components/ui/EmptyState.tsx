import React from "react";
import { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="relative flex flex-col items-center justify-center p-12 text-center border border-[#232630] rounded-xl bg-[#13151b] overflow-hidden">
      <div className="h-12 w-12 rounded-xl bg-zinc-900/90 border border-zinc-800 flex items-center justify-center text-zinc-400 mb-4 shadow-subtle">
        <Icon className="h-5 w-5 text-zinc-300" />
      </div>
      <h3 className="text-sm font-semibold text-zinc-100">{title}</h3>
      <p className="mt-1.5 text-xs text-zinc-400 max-w-sm leading-relaxed">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-5 inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold text-zinc-950 bg-zinc-100 hover:bg-white active:scale-[0.98] transition-all shadow-sm"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

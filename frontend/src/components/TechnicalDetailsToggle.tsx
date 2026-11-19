import React, { useState } from "react";
import { ChevronDown, ChevronRight, GraduationCap } from "lucide-react";

export function TechnicalDetailsToggle({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-slate-50/70 border border-slate-200 rounded-xl overflow-hidden no-print">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3 flex items-center justify-between gap-2 text-left hover:bg-slate-100/80 transition cursor-pointer"
      >
        <div className="flex items-center gap-2 min-w-0">
          <GraduationCap className="w-4 h-4 text-slate-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-bold text-slate-700">{title}</div>
            {subtitle && <div className="text-[11px] text-slate-500 truncate">{subtitle}</div>}
          </div>
        </div>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 shrink-0">
          {open ? "Hide" : "Show"}
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
      </button>
      {open && <div className="p-4 border-t border-slate-200 bg-white space-y-3">{children}</div>}
    </div>
  );
}

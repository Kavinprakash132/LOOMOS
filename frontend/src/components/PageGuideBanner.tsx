import { useEffect, useState } from "react";
import { HelpCircle, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const STORAGE_KEY = "loomos_hide_page_guides";

export function PageGuideBanner({
  steps,
  tip,
}: {
  steps?: string[];
  tip?: string;
}) {
  const { tr } = useAuth();
  const [hidden, setHidden] = useState<boolean>(() => {
    try {
      const val = localStorage.getItem(STORAGE_KEY);
      return val === null ? true : val === "1";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    const onSync = () => {
      try {
        const val = localStorage.getItem(STORAGE_KEY);
        setHidden(val === null ? true : val === "1");
      } catch {
        // ignore storage errors
      }
    };
    window.addEventListener("loomos-guide-toggle", onSync);
    return () => window.removeEventListener("loomos-guide-toggle", onSync);
  }, []);

  const toggle = (nextHidden: boolean) => {
    setHidden(nextHidden);
    try {
      localStorage.setItem(STORAGE_KEY, nextHidden ? "1" : "0");
    } catch {
      // ignore
    }
    window.dispatchEvent(new Event("loomos-guide-toggle"));
  };

  if (hidden) {
    return (
      <div className="flex justify-end no-print -mt-2">
        <button
          type="button"
          onClick={() => toggle(false)}
          className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 cursor-pointer"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          {tr("Show simple guide", "எளிய வழிகாட்டியைக் காட்டு")}
        </button>
      </div>
    );
  }

  return (
    <div className="bg-sky-50/80 border border-sky-200 rounded-xl px-4 py-2.5 flex items-start justify-between gap-3 text-xs text-sky-950 no-print">
      <div className="flex items-start gap-2 leading-relaxed">
        <HelpCircle className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          {steps && steps.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 font-medium">
              {steps.map((s, idx) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded-full bg-white border border-sky-200 text-sky-900 font-semibold">
                    {idx + 1}. {s}
                  </span>
                  {idx < steps.length - 1 && <span className="text-sky-400">→</span>}
                </span>
              ))}
            </div>
          )}
          {tip && <p className="text-sky-900/90">{tip}</p>}
        </div>
      </div>
      <button
        type="button"
        onClick={() => toggle(true)}
        className="text-sky-700 hover:text-sky-950 inline-flex items-center gap-0.5 shrink-0 font-semibold cursor-pointer"
        title={tr("Hide helper tips on all pages", "எல்லா பக்கங்களிலும் குறிப்புகளை மறை")}
      >
        <X className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{tr("Hide tips", "மறை")}</span>
      </button>
    </div>
  );
}

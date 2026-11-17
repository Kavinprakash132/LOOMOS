import { FlaskConical } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function DemoBanner() {
  const { setupStatus } = useAuth();
  if (!setupStatus?.is_demo_mode) return null;

  return (
    <div className="bg-amber-400 text-slate-950 px-3 py-1.5 text-xs font-bold flex items-center justify-center gap-2 border-b border-amber-500 no-print">
      <FlaskConical className="w-4 h-4 shrink-0" />
      <span>
        DEMO DATA ACTIVE ({setupStatus.active_db_name}) — Isolated test sandbox. Your real database (loomos.db) is untouched.
      </span>
    </div>
  );
}

import { useAuth } from "../context/AuthContext";

export function PlaceholderStepPage({ title }: { title: string }) {
  const { t } = useAuth();
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-2">
      <h1 className="text-xl font-bold text-slate-900">{title}</h1>
      <p className="text-sm text-slate-600">{t("step2ComingSoon")}</p>
    </div>
  );
}

import React, { useState } from "react";
import { apiRequest, formatDateDMY, formatRupeesFromPaise, localIsoDate } from "../../api/client";
import { ConfirmVoidModal } from "../ConfirmVoidModal";
import { SlipLangCode, WageMode, Weaver, WeaverRoleType } from "../../types/api";

const ROLE_LABELS: Record<WeaverRoleType, string> = {
  WEAVER: "Weaver",
  PIRN_WINDER: "Pirn Winder",
  HELPER: "Helper",
  FITTER: "Loom Fitter",
};

export function WeaversTab({
  weavers,
  onRefresh,
  onError,
}: {
  weavers: Weaver[];
  onRefresh: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [slipLang, setSlipLang] = useState<SlipLangCode>("ta");
  const [roleType, setRoleType] = useState<WeaverRoleType>("WEAVER");
  const [phone, setPhone] = useState("");
  const [wageMode, setWageMode] = useState<WageMode>("PER_LOOM_SHIFT");
  const [rateRupees, setRateRupees] = useState("60");
  const [effDate, setEffDate] = useState(localIsoDate());

  const [reviseTarget, setReviseTarget] = useState<number | null>(null);
  const [revMode, setRevMode] = useState<WageMode>("PER_LOOM_SHIFT");
  const [revRate, setRevRate] = useState("65");
  const [revDate, setRevDate] = useState(localIsoDate());
  const [voidRuleId, setVoidRuleId] = useState<number | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/weavers", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          preferred_slip_lang: slipLang,
          role_type: roleType,
          phone,
          wage_mode: wageMode,
          rate_paise: Math.round(parseFloat(rateRupees) * 100),
          effective_from: effDate,
        }),
      });
      setFullName("");
      setPhone("");
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to create worker");
    }
  };

  const handleReviseRate = async (e: React.FormEvent, weaverId: number) => {
    e.preventDefault();
    try {
      await apiRequest(`/weavers/${weaverId}/wage-rules`, {
        method: "POST",
        body: JSON.stringify({
          wage_mode: revMode,
          rate_paise: Math.round(parseFloat(revRate) * 100),
          effective_from: revDate,
        }),
      });
      setReviseTarget(null);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to update wage rule");
    }
  };

  const confirmRemoveRule = async (reason: string) => {
    if (!voidRuleId) return;
    try {
      await apiRequest(`/wage-rules/${voidRuleId}`, {
        method: "DELETE",
        body: JSON.stringify({ reason }),
      });
      setVoidRuleId(null);
      await onRefresh();
    } catch (err) {
      setVoidRuleId(null);
      onError(err instanceof Error ? err.message : "Failed to remove rule");
    }
  };

  return (
    <div className="space-y-4">
      <ConfirmVoidModal
        open={voidRuleId !== null}
        title="Remove Wage Rule?"
        description="Removes this wage rule from future calculations while keeping past wage slip records safe."
        confirmLabel="Remove Rule"
        onCancel={() => setVoidRuleId(null)}
        onConfirm={confirmRemoveRule}
      />

      <form onSubmit={handleCreate} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
        <h3 className="text-sm font-bold">Add Worker (Weaver / Pirn Winder / Helper)</h3>
        <div className="grid sm:grid-cols-3 gap-2.5">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Worker Name <span className="text-rose-600">*</span>
            </label>
            <input
              required
              placeholder="e.g. Arumugam K"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Worker Type</label>
            <select
              value={roleType}
              onChange={(e) => setRoleType(e.target.value as WeaverRoleType)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
            >
              <option value="WEAVER">Weaver</option>
              <option value="PIRN_WINDER">Pirn Winder</option>
              <option value="HELPER">Helper</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Payslip Print Language</label>
            <select
              value={slipLang}
              onChange={(e) => setSlipLang(e.target.value as SlipLangCode)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
            >
              <option value="en">English</option>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="hi">Hindi (हिन्दी)</option>
            </select>
          </div>
        </div>
        <div className="grid sm:grid-cols-4 gap-2.5">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Wage Calculation Mode</label>
            <select
              value={wageMode}
              onChange={(e) => setWageMode(e.target.value as WageMode)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
            >
              <option value="PER_LOOM_SHIFT">Per Loom-Shift (₹)</option>
              <option value="PER_METRE">Per Metre (₹/m)</option>
              <option value="PER_SHIFT_ATTENDANCE">Per Shift Attended (₹)</option>
              <option value="FIXED_WEEKLY">Fixed Weekly Pay (₹)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Pay Rate (₹) <span className="text-rose-600">*</span>
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              placeholder="e.g. 60"
              value={rateRupees}
              onChange={(e) => setRateRupees(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Effective From Date</label>
            <input
              type="date"
              value={effDate}
              onChange={(e) => setEffDate(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Phone Number (optional)</label>
            <input
              placeholder="e.g. 9894011111"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
          Add Worker
        </button>
      </form>

      <div className="space-y-2.5">
        {weavers.map((w) => (
          <div key={w.id} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="font-bold text-slate-900">{w.full_name}</span>
                <span className="ml-2 px-2 py-0.5 rounded bg-slate-100 text-[11px] font-semibold">
                  {ROLE_LABELS[w.role_type] ?? w.role_type}
                </span>
                <span className="ml-1.5 px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-[11px] font-semibold uppercase">
                  Slip: {w.preferred_slip_lang}
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setReviseTarget(reviseTarget === w.id ? null : w.id);
                  if (w.wage_rules[0]) {
                    setRevMode(w.wage_rules[0].wage_mode);
                    setRevRate((w.wage_rules[0].rate_paise / 100).toFixed(2));
                  }
                }}
                className="text-xs font-semibold text-amber-700 hover:underline cursor-pointer"
              >
                + Revise Rate (Dated)
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-1">
              {w.wage_rules.map((r) => (
                <div key={r.id} className="flex items-center justify-between bg-slate-50 px-2.5 py-1.5 rounded">
                  <span>
                    <b>{r.wage_mode}</b> · {formatRupeesFromPaise(r.rate_paise)} · From{" "}
                    {formatDateDMY(r.effective_from)}{" "}
                    {r.effective_to ? `to ${formatDateDMY(r.effective_to)}` : "(Active)"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setVoidRuleId(r.id)}
                    className="text-rose-600 hover:underline cursor-pointer font-semibold"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            {reviseTarget === w.id && (
              <form
                onSubmit={(e) => void handleReviseRate(e, w.id)}
                className="pt-2 border-t border-slate-200 grid sm:grid-cols-4 gap-2 items-end"
              >
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 mb-0.5">Wage Mode</label>
                  <select
                    value={revMode}
                    onChange={(e) => setRevMode(e.target.value as WageMode)}
                    className="w-full px-2 py-1.5 rounded border border-slate-300 text-xs"
                  >
                    <option value="PER_LOOM_SHIFT">Per Loom-Shift</option>
                    <option value="PER_METRE">Per Metre</option>
                    <option value="PER_SHIFT_ATTENDANCE">Per Shift Attended</option>
                    <option value="FIXED_WEEKLY">Fixed Weekly</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 mb-0.5">New Rate (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={revRate}
                    onChange={(e) => setRevRate(e.target.value)}
                    className="w-full px-2 py-1.5 rounded border border-slate-300 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 mb-0.5">Effective Date</label>
                  <input
                    type="date"
                    required
                    value={revDate}
                    onChange={(e) => setRevDate(e.target.value)}
                    className="w-full px-2 py-1.5 rounded border border-slate-300 text-xs"
                  />
                </div>
                <button type="submit" className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs font-semibold">
                  Save New Rule
                </button>
              </form>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

import React, { useState } from "react";
import { apiRequest, formatRupeesFromPaise, localIsoDate } from "../../api/client";
import { ConfirmVoidModal } from "../ConfirmVoidModal";
import { EbTariffPlan, StopReason, UnitSettings } from "../../types/api";

export function EbAndStopsTab({
  plans,
  stops,
  settings,
  onRefresh,
  onError,
}: {
  plans: EbTariffPlan[];
  stops: StopReason[];
  settings: UnitSettings | null;
  onRefresh: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const [planName, setPlanName] = useState("");
  const [cycleDays, setCycleDays] = useState(60);
  const [effDate, setEffDate] = useState(localIsoDate());
  const [fixedKwRs, setFixedKwRs] = useState("110.00");
  const [eTaxPct, setETaxPct] = useState("5.00");
  const [fppcaRs, setFppcaRs] = useState("0.00");
  const [slabsText, setSlabsText] = useState("0-1000:0.00, 1001-1500:4.15, 1501+:5.30");

  const [stopCode, setStopCode] = useState("");
  const [stopEn, setStopEn] = useState("");
  const [stopTa, setStopTa] = useState("");
  const [isPowerCut, setIsPowerCut] = useState(false);
  const [voidPlanId, setVoidPlanId] = useState<number | null>(null);

  const createPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const slabs = slabsText.split(",").map((chunk) => {
        const [range, rateStr] = chunk.trim().split(":");
        const ratePaise = Math.round(parseFloat(rateStr) * 100);
        if (range.endsWith("+")) {
          return { min_unit: parseInt(range.slice(0, -1), 10), max_unit: null, rate_paise_per_unit: ratePaise };
        }
        const [mn, mx] = range.split("-").map((x) => parseInt(x, 10));
        return { min_unit: mn, max_unit: mx, rate_paise_per_unit: ratePaise };
      });
      await apiRequest("/eb-tariffs", {
        method: "POST",
        body: JSON.stringify({
          name: planName,
          billing_cycle_days: cycleDays,
          overhead_per_kw_paise: 0,
          fixed_charge_per_kw_month_paise: Math.round(parseFloat(fixedKwRs || "0") * 100),
          electricity_tax_bps: Math.round(parseFloat(eTaxPct || "0") * 100),
          fppca_paise_per_unit: Math.round(parseFloat(fppcaRs || "0") * 100),
          effective_from: effDate,
          slabs,
        }),
      });
      setPlanName("");
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Invalid tariff slab format");
    }
  };

  const activatePlan = async (planId: number) => {
    try {
      await apiRequest("/settings", { method: "PATCH", body: JSON.stringify({ active_tariff_plan_id: planId }) });
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to activate plan");
    }
  };

  const confirmRemovePlan = async (reason: string) => {
    if (!voidPlanId) return;
    try {
      await apiRequest(`/eb-tariffs/${voidPlanId}`, { method: "DELETE", body: JSON.stringify({ reason }) });
      setVoidPlanId(null);
      await onRefresh();
    } catch (err) {
      setVoidPlanId(null);
      onError(err instanceof Error ? err.message : "Failed to remove plan");
    }
  };

  const addStopReason = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/stop-reasons", {
        method: "POST",
        body: JSON.stringify({
          code: stopCode.toUpperCase().replace(/\s+/g, "_"),
          label_en: stopEn,
          label_ta: stopTa,
          is_power_cut: isPowerCut,
        }),
      });
      setStopCode("");
      setStopEn("");
      setStopTa("");
      setIsPowerCut(false);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add stop reason");
    }
  };

  return (
    <div className="space-y-6">
      <ConfirmVoidModal
        open={voidPlanId !== null}
        title="Remove EB Tariff Plan?"
        description="Archives this tariff plan while preserving historical EB bill calculations."
        confirmLabel="Remove Tariff Plan"
        onCancel={() => setVoidPlanId(null)}
        onConfirm={confirmRemovePlan}
      />

      <div className="space-y-3">
        <form onSubmit={createPlan} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">EB Tariff Plans (TANGEDCO / Custom Slab Rates)</h3>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Tariff Plan Name <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. TANGEDCO 2027"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Billing Cycle (Days)</label>
              <input
                type="number"
                min={1}
                value={cycleDays}
                onChange={(e) => setCycleDays(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Effective Date</label>
              <input
                type="date"
                value={effDate}
                onChange={(e) => setEffDate(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fixed Charge (₹/kW/month)</label>
              <input
                type="number"
                step="0.01"
                value={fixedKwRs}
                onChange={(e) => setFixedKwRs(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Electricity Tax (%)</label>
              <input
                type="number"
                step="0.01"
                value={eTaxPct}
                onChange={(e) => setETaxPct(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">FPPCA Charge (₹/unit)</label>
              <input
                type="number"
                step="0.01"
                value={fppcaRs}
                onChange={(e) => setFppcaRs(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Unit Slabs (format: min-max:₹/unit) <span className="text-rose-600">*</span>
            </label>
            <input
              required
              value={slabsText}
              onChange={(e) => setSlabsText(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-xs font-mono"
              placeholder="0-1000:0.00, 1001-1500:4.15, 1501+:5.30"
            />
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
            Add Tariff Plan
          </button>
        </form>

        <div className="space-y-2">
          {plans.map((p) => {
            const isActive = settings?.active_tariff_plan_id === p.id;
            return (
              <div key={p.id} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-sm">{p.name}</span>
                    {isActive && (
                      <span className="ml-2 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div className="flex gap-3 text-xs font-semibold">
                    {!isActive && (
                      <>
                        <button type="button" onClick={() => void activatePlan(p.id)} className="text-amber-700 hover:underline cursor-pointer">
                          Set Active
                        </button>
                        <button type="button" onClick={() => setVoidPlanId(p.id)} className="text-rose-600 hover:underline cursor-pointer">
                          Remove
                        </button>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                  {p.slabs.map((s) => (
                    <span key={s.id} className="px-2 py-1 rounded bg-slate-100 font-mono">
                      {s.min_unit}–{s.max_unit ?? "∞"} u: {formatRupeesFromPaise(s.rate_paise_per_unit)}/u
                    </span>
                  ))}
                  <span className="px-2 py-1 rounded bg-blue-50 text-blue-800">
                    Fixed: {formatRupeesFromPaise(p.fixed_charge_per_kw_month_paise)}/kW/mo · E-Tax: {(p.electricity_tax_bps / 100).toFixed(2)}% · FPPCA: {formatRupeesFromPaise(p.fppca_paise_per_unit)}/u
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stop Reasons */}
      <div className="space-y-3">
        <form onSubmit={addStopReason} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">Stoppage Reasons (Optional Reference Categories)</h3>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Short Code *</label>
              <input
                required
                placeholder="e.g. REED_CHANGE"
                value={stopCode}
                onChange={(e) => setStopCode(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">English Label *</label>
              <input
                required
                placeholder="e.g. Reed Change"
                value={stopEn}
                onChange={(e) => setStopEn(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Tamil Label *</label>
              <input
                required
                placeholder="e.g. ரீட் மாற்றம்"
                value={stopTa}
                onChange={(e) => setStopTa(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700">
            <input type="checkbox" checked={isPowerCut} onChange={(e) => setIsPowerCut(e.target.checked)} />
            Count duration as Power Cut (adjusts EB analysis)
          </label>
          <div>
            <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
              Add Stop Reason
            </button>
          </div>
        </form>

        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {stops.map((s) => (
            <div key={s.id} className="px-4 py-2 flex items-center justify-between text-xs">
              <div>
                <span className="font-mono font-bold mr-2">{s.code}</span>
                <span>{s.label_en} / {s.label_ta}</span>
              </div>
              {s.is_power_cut && (
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">POWER CUT</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

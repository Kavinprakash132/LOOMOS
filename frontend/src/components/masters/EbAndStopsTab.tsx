import React, { useState } from "react";
import { apiRequest, formatRupeesFromPaise, localIsoDate } from "../../api/client";
import { ConfirmVoidModal } from "../ConfirmVoidModal";
import { useAuth } from "../../context/AuthContext";
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
  const { tr } = useAuth();
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
        const parts = chunk.trim().split(":");
        if (parts.length !== 2) throw new Error("Invalid slab entry; use range:rate (e.g. 0-1000:0)");
        const [range, rateStr] = parts;
        const ratePaise = Math.round(parseFloat(rateStr) * 100);
        if (!Number.isFinite(ratePaise) || ratePaise < 0) throw new Error("Invalid slab rate");
        if (range.endsWith("+")) {
          const mn = parseInt(range.slice(0, -1), 10);
          if (!Number.isFinite(mn)) throw new Error("Invalid slab range");
          return { min_unit: mn, max_unit: null, rate_paise_per_unit: ratePaise };
        }
        const [mn, mx] = range.split("-").map((x) => parseInt(x, 10));
        if (!Number.isFinite(mn) || !Number.isFinite(mx)) throw new Error("Invalid slab range");
        return { min_unit: mn, max_unit: mx, rate_paise_per_unit: ratePaise };
      });
      const safePaise = (v: string) => {
        const n = parseFloat(v || "0");
        return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : 0;
      };
      await apiRequest("/eb-tariffs", {
        method: "POST",
        body: JSON.stringify({
          name: planName,
          billing_cycle_days: cycleDays,
          overhead_per_kw_paise: 0,
          fixed_charge_per_kw_month_paise: safePaise(fixedKwRs),
          electricity_tax_bps: safePaise(eTaxPct),
          fppca_paise_per_unit: safePaise(fppcaRs),
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
        title={tr("Remove EB Tariff Plan?", "EB கட்டணத் திட்டத்தை நீக்கவா?")}
        description={tr(
          "Archives this tariff plan while preserving historical EB bill calculations.",
          "இந்தத் திட்டம் நிறுத்தப்படும்; பழைய EB பில் கணக்குகள் பாதுகாப்பாக இருக்கும்."
        )}
        confirmLabel={tr("Remove Tariff Plan", "திட்டத்தை நீக்கு")}
        onCancel={() => setVoidPlanId(null)}
        onConfirm={confirmRemovePlan}
      />

      <div className="space-y-3">
        <form onSubmit={createPlan} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">{tr("EB Tariff Plans (TANGEDCO / Custom Slab Rates)", "EB கட்டணத் திட்டங்கள் (TNPDCL / அடுக்கு கட்டணம்)")}</h3>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Tariff Plan Name", "திட்டப் பெயர்")} <span className="text-rose-600">*</span>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Billing Cycle (Days)", "பில் சுழற்சி (நாட்கள்)")}</label>
              <input
                type="number"
                min={1}
                value={cycleDays}
                onChange={(e) => setCycleDays(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Effective Date", "அமல் தேதி")}</label>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Fixed Charge (₹/kW/month)", "நிலை கட்டணம் (₹/kW/மாதம்)")}</label>
              <input
                type="number"
                step="0.01"
                value={fixedKwRs}
                onChange={(e) => setFixedKwRs(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Electricity Tax (%)", "மின் வரி (%)")}</label>
              <input
                type="number"
                step="0.01"
                value={eTaxPct}
                onChange={(e) => setETaxPct(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("FPPCA Charge (₹/unit)", "FPPCA (₹/யூனிட்)")}</label>
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
              {tr("Unit Slabs (format: min-max:₹/unit)", "யூனிட் அடுக்குகள் (min-max:₹/unit)")} <span className="text-rose-600">*</span>
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
            {tr("Add Tariff Plan", "திட்டம் சேர்")}
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
                        {tr("ACTIVE", "செயலில்")}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-3 text-xs font-semibold">
                    {!isActive && (
                      <>
                        <button type="button" onClick={() => void activatePlan(p.id)} className="text-amber-700 hover:underline cursor-pointer">
                          {tr("Set Active", "செயல்படுத்து")}
                        </button>
                        <button type="button" onClick={() => setVoidPlanId(p.id)} className="text-rose-600 hover:underline cursor-pointer">
                          {tr("Remove", "நீக்கு")}
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
                    {tr("Fixed", "நிலை")}: {formatRupeesFromPaise(p.fixed_charge_per_kw_month_paise)}/kW/mo · E-Tax: {(p.electricity_tax_bps / 100).toFixed(2)}% · FPPCA: {formatRupeesFromPaise(p.fppca_paise_per_unit)}/u
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
          <h3 className="text-sm font-bold">{tr("Stoppage Reasons (Optional Reference Categories)", "நிறுத்தக் காரணங்கள் (விருப்ப வகைகள்)")}</h3>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Short Code *", "குறியீடு *")}</label>
              <input
                required
                placeholder="e.g. REED_CHANGE"
                value={stopCode}
                onChange={(e) => setStopCode(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("English Label *", "ஆங்கிலப் பெயர் *")}</label>
              <input
                required
                placeholder="e.g. Reed Change"
                value={stopEn}
                onChange={(e) => setStopEn(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Tamil Label *", "தமிழ்ப் பெயர் *")}</label>
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
            {tr("Count duration as Power Cut (adjusts EB analysis)", "மின்வெட்டு நேரமாக கணக்கிடு (EB பகுப்பாய்வில்)")}
          </label>
          <div>
            <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
              {tr("Add Stop Reason", "காரணம் சேர்")}
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
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">{tr("POWER CUT", "மின்வெட்டு")}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

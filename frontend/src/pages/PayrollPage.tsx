import React, { useCallback, useEffect, useState } from "react";
import { Download, Printer, ReceiptIndianRupee, Trash2, Wallet, X } from "lucide-react";
import {
  apiRequest,
  downloadProtectedFile,
  formatDateDMY,
  formatRupeesFromPaise,
  localIsoDate,
  offsetLocalIsoDate,
} from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useLiveRefresh } from "../hooks/useLiveRefresh";
import {
  AdvanceRecord,
  PayslipLinePreview,
  PayslipRecord,
  PrintablePayslip,
  SlipLangCode,
  Weaver,
} from "../types/api";

export function PayrollPage() {
  const { t, tr } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<"calc" | "advances" | "slips">("calc");
  const [weavers, setWeavers] = useState<Weaver[]>([]);
  const [advances, setAdvances] = useState<AdvanceRecord[]>([]);
  const [slips, setSlips] = useState<PayslipRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Payroll period
  const [periodStart, setPeriodStart] = useState(offsetLocalIsoDate(-6));
  const [periodEnd, setPeriodEnd] = useState(localIsoDate());
  const [deductAdv, setDeductAdv] = useState(true);
  const [defectRupees, setDefectRupees] = useState<Record<number, string>>({});
  const [preview, setPreview] = useState<PayslipLinePreview[]>([]);

  // Advance form
  const [advWeaverId, setAdvWeaverId] = useState<number>(0);
  const [advDate, setAdvDate] = useState(localIsoDate());
  const [advAmountRs, setAdvAmountRs] = useState("500");
  const [advNote, setAdvNote] = useState("");

  // Printable slip modal
  const [printable, setPrintable] = useState<PrintablePayslip | null>(null);
  const [voidTarget, setVoidTarget] = useState<{ kind: "advance" | "payslip"; id: number; label: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [wv, adv, sl] = await Promise.all([
        apiRequest<Weaver[]>("/weavers"),
        apiRequest<AdvanceRecord[]>("/advances"),
        apiRequest<PayslipRecord[]>("/payslips"),
      ]);
      setWeavers(wv);
      setAdvances(adv);
      setSlips(sl);
      if (!advWeaverId && wv[0]) setAdvWeaverId(wv[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load payroll data");
    }
  }, [advWeaverId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useLiveRefresh(loadAll);

  const getRowDefectPaise = (p: PayslipLinePreview): number => {
    const raw = defectRupees[p.weaver_id];
    if (raw === undefined) return p.defect_deduction_paise;
    const parsed = parseFloat(raw || "0");
    return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed * 100) : 0;
  };

  const getRowNetPaise = (p: PayslipLinePreview): number => {
    return Math.max(0, p.gross_paise - p.advance_deducted_paise - getRowDefectPaise(p));
  };

  const handleCalculate = useCallback(async () => {
    setError(null);
    setSuccess(null);
    try {
      const dedPaise: Record<number, number> = {};
      for (const [wid, val] of Object.entries(defectRupees)) {
        const parsed = parseFloat(val || "0");
        if (parsed > 0) dedPaise[Number(wid)] = Math.round(parsed * 100);
      }
      const res = await apiRequest<PayslipLinePreview[]>("/payslips/preview", {
        method: "POST",
        body: JSON.stringify({
          period_start: periodStart,
          period_end: periodEnd,
          deduct_period_advances: deductAdv,
          defect_deductions_paise: dedPaise,
        }),
      });
      setPreview(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not calculate wages");
    }
  }, [defectRupees, deductAdv, periodEnd, periodStart]);

  useEffect(() => {
    // Auto-load initial 7-day wages preview once on mount
    void handleCalculate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFinalize = async () => {
    if (preview.length === 0 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/payslips/finalize", {
        method: "POST",
        body: JSON.stringify({
          period_start: periodStart,
          period_end: periodEnd,
          items: preview.map((p) => ({
            weaver_id: p.weaver_id,
            wage_mode_snapshot: p.wage_mode,
            units_worked: p.units_worked,
            rate_paise_snapshot: p.rate_paise,
            gross_paise: p.gross_paise,
            advance_deducted_paise: p.advance_deducted_paise,
            defect_deduction_paise: getRowDefectPaise(p),
          })),
        }),
      });
      setPreview([]);
      const msg = tr("Finalized payslips saved.", "இறுதி சம்பள சீட்டுகள் சேமிக்கப்பட்டன.");
      setSuccess(msg);
      toast.success(msg);
      setTab("slips");
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to finalize payslips", "சம்பள சீட்டுகளை இறுதி செய்ய முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateAdvance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const advNum = parseFloat(advAmountRs);
    if (!Number.isFinite(advNum) || advNum <= 0) {
      const msg = tr("Enter a valid advance amount.", "சரியான முன்பண தொகையை உள்ளிடவும்.");
      setError(msg);
      toast.error(msg);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/advances", {
        method: "POST",
        body: JSON.stringify({
          weaver_id: advWeaverId,
          advance_date: advDate,
          amount_paise: Math.round(advNum * 100),
          note: advNote || null,
        }),
      });
      setAdvNote("");
      const msg = tr("Advance recorded.", "முன்பணம் பதிவு செய்யப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to record advance", "முன்பணத்தை பதிவு செய்ய முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmVoidPayrollItem = async (reason: string) => {
    if (!voidTarget) return;
    setError(null);
    const endpoint =
      voidTarget.kind === "advance" ? `/advances/${voidTarget.id}` : `/payslips/${voidTarget.id}`;
    try {
      await apiRequest(endpoint, { method: "DELETE", body: JSON.stringify({ reason }) });
      const label = voidTarget.label;
      setVoidTarget(null);
      const msg = tr(`Voided ${label}.`, `${label} நீக்கப்பட்டது.`);
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      setVoidTarget(null);
      const msg = err instanceof Error ? err.message : tr(`Failed to void ${voidTarget.label}`, `${voidTarget.label} நீக்க முடியவில்லை`);
      setError(msg);
      toast.error(msg);
    }
  };

  const openPrintSlip = async (slipId: number, overrideLang?: SlipLangCode) => {
    setError(null);
    try {
      const qs = overrideLang ? `?lang=${overrideLang}` : "";
      const data = await apiRequest<PrintablePayslip>(`/payslips/${slipId}/printable${qs}`);
      setPrintable(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("Failed to load printable payslip", "சம்பள சீட்டை ஏற்ற முடியவில்லை"));
    }
  };

  return (
    <div className="space-y-5">
      <ConfirmVoidModal
        open={Boolean(voidTarget)}
        title={tr(`Void ${voidTarget?.label ?? ""}?`, `${voidTarget?.label ?? ""} பதிவை நீக்கவா?`)}
        description={tr("Marks this entry void while preserving a change log entry.", "இந்த பதிவு நீக்கப்படும்; ஆனால் மாற்றப் பதிவில் வரலாறு இருக்கும்.")}
        confirmLabel={tr("Confirm Void", "நீக்குதலை உறுதி செய்")}
        onCancel={() => setVoidTarget(null)}
        onConfirm={confirmVoidPayrollItem}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 no-print">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Wallet className="w-5 h-5 text-amber-600" />
            {tr("4-Mode Payroll, Advances & Multilingual Payslips", "தொழிலாளர் கூலி, அட்வான்ஸ் (உதாவ்) & சம்பள ரசீதுகள்")}
          </h1>
          <p className="text-xs text-slate-500">
            {tr(
              "Supports Per Metre, Per Loom-Shift, Per Shift Attended, Fixed Weekly & EN / தமிழ் / हिन्दी PDF slips.",
              "மீட்டர் கூலி, தறி-ஷிப்ட், வருகை ஷிப்ட், வாராந்திர சம்பளம் & EN / தமிழ் / हिन्दी PDF ரசீதுகள்."
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void downloadProtectedFile("/exports/csv/payslips", "loomos_payslips.csv")}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-semibold inline-flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" /> {tr("CSV Payslips", "கூலி CSV")}
          </button>
          <button
            type="button"
            onClick={() => void downloadProtectedFile("/exports/csv/advances", "loomos_advances.csv")}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-semibold inline-flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" /> {tr("CSV Advances", "அட்வான்ஸ் CSV")}
          </button>
        </div>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm no-print">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm no-print">{success}</div>}

      <PageGuideBanner
        steps={[
          tr("Check auto-calculated 7-day wages (adjust Damage Cut if needed)", "7 நாள் கூலியைச் சரிபார்க்கவும் (தேவைப்பட்டால் சேதக் கழிவு சேர்க்கவும்)"),
          tr("Record any Worker Advances (Uthaav)", "தொழிலாளர் அட்வான்ஸ் (உதாவ்) பதிவு செய்யவும்"),
          tr("Finalize & print English / தமிழ் / हिन्दी payslips", "இறுதிசெய்து தமிழ் / English / हिन्दी ரசீது அச்சிடவும்"),
        ]}
      />

      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 no-print">
        {[
          { id: "calc", label: tr("Weekly Wages", "வார கூலி கணக்கீடு") },
          { id: "advances", label: tr(`Advances / Uthaav (${advances.length})`, `அட்வான்ஸ் / உதாவ் (${advances.length})`) },
          { id: "slips", label: tr(`Saved Payslips (${slips.length})`, `இறுதி ரசீதுகள் (${slips.length})`) },
        ].map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id as "calc" | "advances" | "slips")}
            className={`px-3.5 py-2.5 text-xs font-semibold border-b-2 -mb-px transition cursor-pointer ${
              tab === item.id
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Calculate & Finalize */}
      {tab === "calc" && (
        <div className="space-y-4 no-print">
          <div className="bg-white p-4 rounded-xl border border-slate-200 flex flex-wrap items-end gap-3">
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Period Start", "தொடக்க தேதி")}</label>
              <input
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Period End", "முடிவு தேதி")}</label>
              <input
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                className="px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-xs font-medium pb-2">
              <input type="checkbox" checked={deductAdv} onChange={(e) => setDeductAdv(e.target.checked)} />
              {tr("Auto-deduct open Advances (Uthaav)", "அட்வான்ஸ் (உதாவ்) தானாகக் கழிக்கவும்")}
            </label>
            <button
              type="button"
              onClick={() => void handleCalculate()}
              className="px-4 py-2 rounded-lg bg-amber-500 text-slate-950 text-xs font-bold"
            >
              {tr("Calculate Wages Preview", "கூலியைக் கணக்கிடு")}
            </button>
          </div>

          {preview.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
              <div className="flex flex-wrap justify-between items-center gap-2">
                <h2 className="text-sm font-bold">
                  {tr("Payroll Preview", "கூலி முன்னோட்டம்")} ({formatDateDMY(periodStart)} – {formatDateDMY(periodEnd)}) — {tr("Total Net", "மொத்த நிகரம்")}:{" "}
                  {formatRupeesFromPaise(preview.reduce((a, p) => a + getRowNetPaise(p), 0))}
                </h2>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => void handleFinalize()}
                  className="px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-bold inline-flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  <ReceiptIndianRupee className="w-4 h-4" /> {tr("Finalize & Save Slips", "இறுதிசெய்து சேமி")}
                </button>
              </div>
              <p className="text-[11px] text-slate-500">
                <b>{tr("Advance Cut (Uthaav)", "அட்வான்ஸ் கழிவு (உதாவ்)")}</b> = {tr("early money given to worker deducted automatically", "முன்பணம் தானாகக் கழிக்கப்படும்")} ·{" "}
                <b>{tr("Damage Cut (optional)", "சேதக் கழிவு (விருப்பம்)")}</b> = {tr("penalty for damaged cloth (₹).", "சேதமான துணிக்கான பிடித்தம் (₹).")}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">{tr("Worker", "தொழிலாளர்")}</th>
                      <th className="py-2 pr-3">{tr("Mode", "கூலி முறை")}</th>
                      <th className="py-2 pr-3">{tr("Units", "அளவு")}</th>
                      <th className="py-2 pr-3">{tr("Gross", "மொத்தம்")}</th>
                      <th className="py-2 pr-3">{tr("Advance Cut (Uthaav)", "அட்வான்ஸ் கழிவு")}</th>
                      <th className="py-2 pr-3">{tr("Damage Cut (optional ₹)", "சேதக் கழிவு (₹)")}</th>
                      <th className="py-2">{tr("Net Payable", "கைப்பணம்")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.map((p) => (
                      <tr key={p.weaver_id}>
                        <td className="py-2 pr-3 font-semibold">
                          {p.weaver_name}{" "}
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 uppercase">
                            {p.preferred_slip_lang}
                          </span>
                        </td>
                        <td className="py-2 pr-3">{t(`wage_${p.wage_mode}`)}</td>
                        <td className="py-2 pr-3">{p.units_worked}</td>
                        <td className="py-2 pr-3 font-semibold">{formatRupeesFromPaise(p.gross_paise)}</td>
                        <td className="py-2 pr-3 text-amber-700">{formatRupeesFromPaise(p.advance_deducted_paise)}</td>
                        <td className="py-2 pr-3">
                          <input
                            type="number"
                            step="1"
                            min="0"
                            placeholder="0"
                            value={defectRupees[p.weaver_id] ?? ""}
                            onChange={(e) => setDefectRupees((d) => ({ ...d, [p.weaver_id]: e.target.value }))}
                            className="w-20 px-2 py-1 rounded border border-slate-300 text-xs"
                            title={tr("Re-run preview after entering deduction", "கழிவை உள்ளிட்டதும் மீண்டும் கணக்கிடவும்")}
                          />
                        </td>
                        <td className="py-2 font-bold text-emerald-700">
                          {formatRupeesFromPaise(getRowNetPaise(p))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Advances */}
      {tab === "advances" && (
        <div className="space-y-4 no-print">
          <form onSubmit={handleCreateAdvance} className="bg-white p-4 rounded-xl border border-slate-200 grid sm:grid-cols-5 gap-2.5 items-end">
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Worker", "தொழிலாளர்")}</label>
              <select
                required
                value={advWeaverId}
                onChange={(e) => setAdvWeaverId(Number(e.target.value))}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              >
                {weavers.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Date", "தேதி")}</label>
              <input
                type="date"
                required
                value={advDate}
                onChange={(e) => setAdvDate(e.target.value)}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Amount (₹)", "தொகை (₹)")}</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={advAmountRs}
                onChange={(e) => setAdvAmountRs(e.target.value)}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Note (optional)", "குறிப்பு (விருப்பம்)")}</label>
              <input
                value={advNote}
                onChange={(e) => setAdvNote(e.target.value)}
                placeholder={tr("Reason", "காரணம்")}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer">
              {tr("Record Advance", "அட்வான்ஸ் பதிவு")}
            </button>
          </form>

          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {advances.map((a) => (
              <div key={a.id} className="px-4 py-2.5 flex items-center justify-between text-xs">
                <div>
                  <b>{a.weaver_name}</b> · {formatDateDMY(a.advance_date)} ·{" "}
                  <span className="font-bold text-amber-700">{formatRupeesFromPaise(a.amount_paise)}</span>
                  {a.note && <span className="ml-2 text-slate-500">({a.note})</span>}
                </div>
                <button
                  type="button"
                  onClick={() => setVoidTarget({ kind: "advance", id: a.id, label: `Advance for ${a.weaver_name}` })}
                  className="text-rose-600 hover:underline inline-flex items-center gap-1 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" /> {tr("Void", "நீக்கு")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Finalized Payslips */}
      {tab === "slips" && (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 no-print">
          {slips.length === 0 && (
            <div className="p-6 text-xs text-slate-500">{tr("No finalized payslips yet.", "இன்னும் இறுதி செய்யப்பட்ட ரசீதுகள் இல்லை.")}</div>
          )}
          {slips.map((s) => (
            <div key={s.id} className="px-4 py-3 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div>
                <span className="font-bold text-sm">{s.weaver_name}</span>
                <span className="ml-2 text-slate-500">
                  {formatDateDMY(s.period_start)} – {formatDateDMY(s.period_end)} · {t(`wage_${s.wage_mode_snapshot}`)} ({s.units_worked})
                </span>
                <div className="text-slate-600 mt-0.5">
                  {tr("Gross", "மொத்தம்")}: {formatRupeesFromPaise(s.gross_paise)} · {tr("Adv", "உதாவ்")}: {formatRupeesFromPaise(s.advance_deducted_paise)} ·{" "}
                  {tr("Net", "நிகரம்")}: <b className="text-emerald-700">{formatRupeesFromPaise(s.net_payable_paise)}</b>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void openPrintSlip(s.id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 text-white font-semibold inline-flex items-center gap-1"
                >
                  <Printer className="w-3.5 h-3.5" /> {tr("Print / PDF", "அச்சு / PDF")} ({s.preferred_slip_lang.toUpperCase()})
                </button>
                <button
                  type="button"
                  onClick={() => setVoidTarget({ kind: "payslip", id: s.id, label: `Payslip for ${s.weaver_name}` })}
                  className="text-rose-600 hover:underline cursor-pointer"
                >
                  {tr("Void", "நீக்கு")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Trilingual HTML @media print Payslip Modal (English / Tamil / Hindi) */}
      {printable && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-3 no-print">
              <div className="flex gap-1.5 text-xs font-semibold">
                {(["en", "ta", "hi"] as SlipLangCode[]).map((l) => (
                  <button
                    key={l}
                    type="button"
                    onClick={() => void openPrintSlip(printable.payslip.id, l)}
                    className={`px-2.5 py-1 rounded border ${
                      printable.lang === l ? "bg-amber-500 text-slate-950 border-amber-500" : "bg-white border-slate-300"
                    }`}
                  >
                    {l === "en" ? "English" : l === "ta" ? "தமிழ்" : "हिन्दी"}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-3.5 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-bold inline-flex items-center gap-1"
                >
                  <Printer className="w-3.5 h-3.5" /> Print / Save PDF
                </button>
                <button type="button" onClick={() => setPrintable(null)} className="p-1 text-slate-500">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="printable-area border border-slate-300 rounded-xl p-5 space-y-3 text-sm">
              <div className="text-center border-b border-slate-200 pb-2">
                <div className="font-bold text-base">{printable.unit_name}</div>
                {printable.unit_location && <div className="text-xs text-slate-500">{printable.unit_location}</div>}
                <div className="font-bold text-amber-800 mt-1">{printable.labels.payslip_title}</div>
              </div>

              <div className="grid grid-cols-2 gap-y-1.5 text-xs">
                <span className="text-slate-500">{printable.labels.weaver}:</span>
                <span className="font-bold text-right">{printable.localized_weaver_name}</span>

                <span className="text-slate-500">{printable.labels.period}:</span>
                <span className="text-right">
                  {formatDateDMY(printable.payslip.period_start)} — {formatDateDMY(printable.payslip.period_end)}
                </span>

                <span className="text-slate-500">{printable.labels.wage_mode}:</span>
                <span className="text-right">{printable.labels[printable.payslip.wage_mode_snapshot]}</span>

                <span className="text-slate-500">{printable.labels.units_worked}:</span>
                <span className="text-right">{printable.payslip.units_worked}</span>

                <span className="text-slate-500">{printable.labels.rate}:</span>
                <span className="text-right">{formatRupeesFromPaise(printable.payslip.rate_paise_snapshot)}</span>

                <span className="text-slate-500">{printable.labels.gross}:</span>
                <span className="font-semibold text-right">
                  {formatRupeesFromPaise(printable.payslip.gross_paise)}
                </span>

                <span className="text-slate-500">{printable.labels.advances}:</span>
                <span className="text-rose-700 text-right">
                  -{formatRupeesFromPaise(printable.payslip.advance_deducted_paise)}
                </span>

                <span className="text-slate-500">{printable.labels.defect_deduction}:</span>
                <span className="text-rose-700 text-right">
                  -{formatRupeesFromPaise(printable.payslip.defect_deduction_paise)}
                </span>
              </div>

              <div className="border-t-2 border-slate-800 pt-2 flex justify-between items-center font-bold text-base">
                <span>{printable.labels.net_payable}</span>
                <span>{formatRupeesFromPaise(printable.payslip.net_payable_paise)}</span>
              </div>

              <div className="pt-4 flex justify-between text-[11px] text-slate-500 border-t border-slate-100">
                <span>
                  {printable.labels.generated_at}: {printable.printed_on}
                </span>
                <span>{printable.labels.signature}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

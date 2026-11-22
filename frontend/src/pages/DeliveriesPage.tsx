import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Database, Download, FileSpreadsheet, Plus, Trash2, Truck, Upload, Zap } from "lucide-react";
import {
  apiRequest,
  downloadProtectedFile,
  formatDateDMY,
  formatHoursFromMins,
  formatRupeesFromPaise,
  localIsoDate,
} from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useLiveRefresh } from "../hooks/useLiveRefresh";
import {
  Beam,
  DeliveryRecord,
  EbBillRecord,
  EbReadingRecord,
  ExpenseRecord,
  FabricSort,
  Trader,
  TraderLedgerSummary,
  TraderPaymentRecord,
} from "../types/api";

type TabId = "deliveries" | "payments" | "expenses" | "eb" | "exports";

function suggestNextChallanNo(existing: DeliveryRecord[]): string {
  let maxNum = 200;
  let prefix = "CH-";
  for (const d of existing) {
    const m = d.challan_no.match(/^([A-Za-z-]+?)(\d+)$/);
    if (m) {
      const n = parseInt(m[2], 10);
      if (n >= maxNum) {
        maxNum = n;
        prefix = m[1];
      }
    }
  }
  return existing.length === 0 ? "CH-001" : `${prefix}${maxNum + 1}`;
}

export function DeliveriesPage() {
  const { tr } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<TabId>("deliveries");
  const [traders, setTraders] = useState<Trader[]>([]);
  const [sorts, setSorts] = useState<FabricSort[]>([]);
  const [beams, setBeams] = useState<Beam[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [payments, setPayments] = useState<TraderPaymentRecord[]>([]);
  const [ledger, setLedger] = useState<TraderLedgerSummary[]>([]);
  const [expenses, setExpenses] = useState<ExpenseRecord[]>([]);
  const [ebReadings, setEbReadings] = useState<EbReadingRecord[]>([]);
  const [ebBills, setEbBills] = useState<EbBillRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [voidTarget, setVoidTarget] = useState<{ endpoint: string; label: string } | null>(null);
  const [showDeliveryForm, setShowDeliveryForm] = useState(false);
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);

  // Delivery form
  const [delTraderId, setDelTraderId] = useState<number>(0);
  const [challanNo, setChallanNo] = useState("");
  const [delDate, setDelDate] = useState(localIsoDate());
  const [delSortId, setDelSortId] = useState<number>(0);
  const [delBeamId, setDelBeamId] = useState<number | "">("");
  const [delPieces, setDelPieces] = useState("10");
  const [delMetres, setDelMetres] = useState("1000");
  const [delRateRs, setDelRateRs] = useState("6.00");

  // Payment form
  const [payTraderId, setPayTraderId] = useState<number>(0);
  const [payDate, setPayDate] = useState(localIsoDate());
  const [payAmtRs, setPayAmtRs] = useState("");
  const [payShortRs, setPayShortRs] = useState("0");
  const [payRef, setPayRef] = useState("");

  // Expense form
  const [expDate, setExpDate] = useState(localIsoDate());
  const [expCategory, setExpCategory] = useState("Spares & Shuttles");
  const [expAmtRs, setExpAmtRs] = useState("");
  const [expNote, setExpNote] = useState("");

  // EB reading & bill forms
  const [readDate, setReadDate] = useState(localIsoDate());
  const [readKwh, setReadKwh] = useState("");
  const [billStart, setBillStart] = useState(localIsoDate());
  const [billEnd, setBillEnd] = useState(localIsoDate());
  const [billUnits, setBillUnits] = useState("");
  const [billNetRs, setBillNetRs] = useState("");
  const [billPowerCutMins, setBillPowerCutMins] = useState("0");

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [tr, sr, bm, dl, py, lg, ex, er, eb] = await Promise.all([
        apiRequest<Trader[]>("/traders"),
        apiRequest<FabricSort[]>("/fabric-sorts"),
        apiRequest<Beam[]>("/beams"),
        apiRequest<DeliveryRecord[]>("/deliveries"),
        apiRequest<TraderPaymentRecord[]>("/payments"),
        apiRequest<TraderLedgerSummary[]>("/traders/ledger"),
        apiRequest<ExpenseRecord[]>("/expenses"),
        apiRequest<EbReadingRecord[]>("/eb-readings"),
        apiRequest<EbBillRecord[]>("/eb-bills"),
      ]);
      setTraders(tr);
      setSorts(sr);
      setBeams(bm);
      setDeliveries(dl);
      setPayments(py);
      setLedger(lg);
      setExpenses(ex);
      setEbReadings(er);
      setEbBills(eb);
      setChallanNo((cur) => (cur ? cur : suggestNextChallanNo(dl)));
      if (!delTraderId && tr[0]) setDelTraderId(tr[0].id);
      if (!payTraderId && tr[0]) setPayTraderId(tr[0].id);
      if (!delSortId && sr[0]) {
        setDelSortId(sr[0].id);
        setDelRateRs((sr[0].agreed_rate_paise / 100).toFixed(2));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load financial records");
    }
  }, [delTraderId, payTraderId, delSortId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useLiveRefresh(loadAll);

  const selectedSort = sorts.find((s) => s.id === delSortId);
  const appliedPaisePreview = Math.round((parseFloat(delRateRs || "0") || 0) * 100);
  const hasInlineRateCut = selectedSort ? appliedPaisePreview > 0 && appliedPaisePreview < selectedSort.agreed_rate_paise : false;

  const submitDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!Number.isFinite(appliedPaisePreview) || appliedPaisePreview <= 0) {
      const msg = tr("Enter a valid rate per metre.", "சரியான மீட்டர் விகிதத்தை உள்ளிடவும்.");
      setError(msg);
      toast.error(msg);
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await apiRequest<DeliveryRecord>("/deliveries", {
        method: "POST",
        body: JSON.stringify({
          trader_id: delTraderId,
          challan_no: challanNo,
          delivery_date: delDate,
          items: [
            {
              beam_id: delBeamId ? Number(delBeamId) : null,
              sort_id: delSortId || null,
              pieces: Number(delPieces),
              metres: delMetres,
              applied_rate_paise: appliedPaisePreview,
            },
          ],
        }),
      });
      const msg = res.has_rate_cut
        ? tr(
            `Challan saved — RATE CUT DETECTED: shortfall ${formatRupeesFromPaise(res.total_underpayment_paise)}!`,
            `சலான் சேமிக்கப்பட்டது — விலை குறைப்பு கண்டறியப்பட்டது: ${formatRupeesFromPaise(res.total_underpayment_paise)}!`
          )
        : tr("Delivery challan saved.", "டெலிவரி சலான் சேமிக்கப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      setShowDeliveryForm(false);
      setChallanNo(suggestNextChallanNo([res, ...deliveries]));
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to create delivery", "டெலிவரியை சேமிக்க முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const submitPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const amtNum = parseFloat(payAmtRs);
    const shortNum = parseFloat(payShortRs || "0");
    if (!Number.isFinite(amtNum) || amtNum <= 0) {
      const msg = tr("Enter a valid payment amount.", "சரியான தொகையை உள்ளிடவும்.");
      setError(msg);
      toast.error(msg);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/payments", {
        method: "POST",
        body: JSON.stringify({
          trader_id: payTraderId,
          payment_date: payDate,
          amount_paise: Math.round(amtNum * 100),
          shortage_deduction_paise: Number.isFinite(shortNum) && shortNum > 0 ? Math.round(shortNum * 100) : 0,
          reference: payRef || null,
        }),
      });
      setPayAmtRs("");
      setPayRef("");
      setShowPaymentForm(false);
      const msg = tr("Trader payment recorded.", "வியாபாரி பணம் பதிவு செய்யப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to save payment", "பணத்தை சேமிக்க முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const submitExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const expNum = parseFloat(expAmtRs);
    if (!Number.isFinite(expNum) || expNum <= 0) {
      const msg = tr("Enter a valid expense amount.", "சரியான செலவு தொகையை உள்ளிடவும்.");
      setError(msg);
      toast.error(msg);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/expenses", {
        method: "POST",
        body: JSON.stringify({
          expense_date: expDate,
          category: expCategory,
          amount_paise: Math.round(expNum * 100),
          note: expNote || null,
        }),
      });
      setExpAmtRs("");
      setExpNote("");
      setShowExpenseForm(false);
      const msg = tr("Expense saved.", "செலவு சேமிக்கப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to save expense", "செலவை சேமிக்க முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const submitEbReading = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/eb-readings", {
        method: "POST",
        body: JSON.stringify({ reading_date: readDate, kwh_total: readKwh }),
      });
      setReadKwh("");
      const msg = tr("EB meter snapshot saved.", "EB மீட்டர் அளவு சேமிக்கப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to save EB reading", "EB அளவை சேமிக்க முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const submitEbBill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const netNum = parseFloat(billNetRs);
    if (!Number.isFinite(netNum) || netNum < 0) {
      const msg = tr("Enter a valid net EB bill amount.", "சரியான EB பில் தொகையை உள்ளிடவும்.");
      setError(msg);
      toast.error(msg);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/eb-bills", {
        method: "POST",
        body: JSON.stringify({
          period_start: billStart,
          period_end: billEnd,
          units_consumed: billUnits,
          net_bill_paise: Math.round(netNum * 100),
          total_power_cut_mins: Number(billPowerCutMins || "0"),
        }),
      });
      setBillUnits("");
      setBillNetRs("");
      const msg = tr("EB bill saved.", "EB பில் சேமிக்கப்பட்டது.");
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to save EB bill", "EB பில்லை சேமிக்க முடியவில்லை");
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const uploadHistoryCsv = async (kind: "eb-bills-csv" | "deliveries-csv", file: File) => {
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await apiRequest(`/imports/${kind}`, { method: "POST", body: fd });
      const msg = `Imported ${file.name} successfully.`;
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      const msg = err instanceof Error ? err.message : `Failed to import ${file.name}`;
      setError(msg);
      toast.error(msg);
    }
  };

  const softDeleteRecord = (endpoint: string, label: string) => {
    setVoidTarget({ endpoint, label });
  };

  const confirmSoftDelete = async (reason: string) => {
    if (!voidTarget) return;
    setError(null);
    try {
      await apiRequest(voidTarget.endpoint, { method: "DELETE", body: JSON.stringify({ reason }) });
      const label = voidTarget.label;
      setVoidTarget(null);
      const msg = tr(`Voided ${label}.`, `${label} நீக்கப்பட்டது.`);
      setSuccess(msg);
      toast.success(msg);
      await loadAll();
    } catch (err) {
      setVoidTarget(null);
      const msg = err instanceof Error ? err.message : `Failed to void ${voidTarget.label}`;
      setError(msg);
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-5">
      <ConfirmVoidModal
        open={Boolean(voidTarget)}
        title={tr(`Void ${voidTarget?.label ?? ""}?`, `${voidTarget?.label ?? ""} பதிவை நீக்கவா?`)}
        description={tr("Removes this record from totals and stores it in Change History.", "இந்த பதிவு மொத்தக் கணக்கிலிருந்து நீக்கப்படும்; மாற்றப் பதிவில் வரலாறு இருக்கும்.")}
        confirmLabel={tr("Confirm Void", "நீக்குதலை உறுதி செய்")}
        onCancel={() => setVoidTarget(null)}
        onConfirm={confirmSoftDelete}
      />
      <div>
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Truck className="w-5 h-5 text-amber-600" />
          {tr("Deliveries, Rate Checker, EB Ledger & Backups", "டெலிவரி, விலை சரிபார்ப்பு, EB கணக்கு & பேக்கப்")}
        </h1>
        <p className="text-xs text-slate-500">
          {tr(
            "Flags trader per-metre rate cuts automatically, tracks receivables, EB bills, and Excel-ready CSV/DB backups.",
            "வியாபாரி விலை குறைப்பை தானாகக் காட்டும்; பாக்கி, EB பில் மற்றும் CSV/DB பேக்கப் பதிவிறக்கலாம்."
          )}
        </p>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      <PageGuideBanner
        tip={tr(
          "Record cloth deliveries (auto-checks if a trader cuts your per-metre rate), log money received, track shed expenses, and save EB meter snapshots or bills.",
          "துணி டெலிவரி (விலை குறைப்பை தானாகச் சரிபார்க்கும்), வரவு பணம், ஆலை செலவுகள் மற்றும் EB மீட்டர்/பில்களை இங்கே பதிவு செய்யவும்."
        )}
      />

      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200">
        {[
          { id: "deliveries", label: tr(`Deliveries (${deliveries.length})`, `டெலிவரி (${deliveries.length})`) },
          { id: "payments", label: tr("Trader Payments", "வியாபாரி வரவு") },
          { id: "expenses", label: tr(`Expenses (${expenses.length})`, `செலவுகள் (${expenses.length})`) },
          { id: "eb", label: tr(`EB Readings & Bills (${ebBills.length})`, `EB பில்கள் (${ebBills.length})`) },
          { id: "exports", label: tr("Exports & Backup", "CSV & பேக்கப்") },
        ].map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id as TabId)}
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

      {/* Tab 1: Deliveries & Rate Checker */}
      {tab === "deliveries" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setShowDeliveryForm((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold cursor-pointer transition ${
                showDeliveryForm
                  ? "bg-slate-900 text-white"
                  : "bg-amber-500 text-slate-950 hover:bg-amber-400 shadow-sm"
              }`}
            >
              <Plus className="w-4 h-4" />
              {showDeliveryForm ? tr("Close Challan Form", "சலான் படிவத்தை மூடு") : tr("Add Delivery Challan", "டெலிவரி சலான் சேர்")}
            </button>
          </div>
          {showDeliveryForm && (
          <form onSubmit={submitDelivery} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm space-y-3">
            <div>
              <h2 className="text-sm font-bold">{tr("Record Cloth Delivery Challan (Rate Checker Active)", "துணி டெலிவரி சலான் பதிவு (விலை சரிபார்ப்பு செயலில்)")}</h2>
              <p className="text-[11px] text-slate-500">
                {tr(
                  "Challan No auto-fills next number (editable if copying a printed slip). Rate Checker compares Applied Rate vs Agreed Sort Rate and flags underpayments automatically.",
                  "சலான் எண் தானாக வரும் (மாற்றலாம்). ஒப்புக்கொண்ட விலையை விடக் குறைவாகப் போட்டால் தானாக எச்சரிக்கும்."
                )}
              </p>
            </div>
            <div className="grid sm:grid-cols-4 gap-2">
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Trader *", "வியாபாரி *")}</label>
                <select
                  required
                  value={delTraderId}
                  onChange={(e) => setDelTraderId(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
                >
                  {traders.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.company_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Challan No (Auto / Editable) *", "சலான் எண் *")}</label>
                <input
                  required
                  placeholder="e.g. CH-203"
                  value={challanNo}
                  onChange={(e) => setChallanNo(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Delivery Date *", "டெலிவரி தேதி *")}</label>
                <input
                  type="date"
                  required
                  value={delDate}
                  onChange={(e) => setDelDate(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Warp Beam (optional)", "பீம் (விருப்பம்)")}</label>
                <select
                  value={delBeamId}
                  onChange={(e) => setDelBeamId(e.target.value ? Number(e.target.value) : "")}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
                >
                  <option value="">{tr("None / Unlinked", "ஏதுமில்லை")}</option>
                  {beams.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.beam_no}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid sm:grid-cols-12 gap-2 items-end">
              <div className="sm:col-span-5">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Fabric Sort *", "துணி வகை *")}</label>
                <select
                  required
                  value={delSortId}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setDelSortId(id);
                    const s = sorts.find((x) => x.id === id);
                    if (s) setDelRateRs((s.agreed_rate_paise / 100).toFixed(2));
                  }}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
                >
                  {sorts.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.sort_name} ({tr("Agreed", "ஒப்பந்தம்")} ₹{(s.agreed_rate_paise / 100).toFixed(2)})
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Pieces (Taakas)", "தக்கா / பீஸ்")}</label>
                <input
                  type="number"
                  min="1"
                  value={delPieces}
                  onChange={(e) => setDelPieces(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Delivered Metres *", "டெலிவரி மீட்டர் *")}</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={delMetres}
                  onChange={(e) => setDelMetres(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div className="sm:col-span-3">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Applied Rate (₹/m) *", "போட்ட விலை (₹/மீ) *")}</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={delRateRs}
                  onChange={(e) => setDelRateRs(e.target.value)}
                  className={`w-full px-3 py-2 rounded border text-sm font-bold ${
                    hasInlineRateCut ? "border-rose-500 bg-rose-50 text-rose-800" : "border-slate-300"
                  }`}
                />
              </div>
            </div>
            {hasInlineRateCut && selectedSort && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                {tr(
                  `Rate cut warning: Applied ₹${delRateRs}/m is below agreed ${formatRupeesFromPaise(selectedSort.agreed_rate_paise)}/m (shortfall ≈ ${formatRupeesFromPaise(Math.round((selectedSort.agreed_rate_paise - appliedPaisePreview) * parseFloat(delMetres || "0")))}).`,
                  `விலை குறைப்பு எச்சரிக்கை: ₹${delRateRs}/மீ என்பது ஒப்பந்த விலை ${formatRupeesFromPaise(selectedSort.agreed_rate_paise)}/மீ-ஐ விடக் குறைவு (இழப்பு ≈ ${formatRupeesFromPaise(Math.round((selectedSort.agreed_rate_paise - appliedPaisePreview) * parseFloat(delMetres || "0")))}).`
                )}
              </div>
            )}
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold cursor-pointer disabled:opacity-50">
              {tr("Save Delivery Challan", "டெலிவரி சலானை சேமி")}
            </button>
          </form>
          )}

          <div className="space-y-2">
            {deliveries.map((d) => (
              <div
                key={d.id}
                className={`bg-white p-3.5 rounded-xl border text-xs flex flex-wrap items-center justify-between gap-2 ${
                  d.has_rate_cut ? "border-rose-300 bg-rose-50/40" : "border-slate-200"
                }`}
              >
                <div>
                  <span className="font-bold text-sm">{d.challan_no}</span> · {d.trader_name} · {formatDateDMY(d.delivery_date)} ·{" "}
                  <b>{d.total_metres} m</b>
                  {d.has_rate_cut && (
                    <span className="ml-2 px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold">
                      {tr("RATE CUT", "விலை குறைப்பு")}: -{formatRupeesFromPaise(d.total_underpayment_paise)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-bold text-slate-900">{formatRupeesFromPaise(d.total_amount_paise)}</span>
                  <button
                    type="button"
                    onClick={() => void softDeleteRecord(`/deliveries/${d.id}`, `Challan ${d.challan_no}`)}
                    className="text-rose-600 hover:underline inline-flex items-center gap-0.5"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> {tr("Void", "நீக்கு")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Payments & Receivables Ledger */}
      {tab === "payments" && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 overflow-x-auto">
            <h2 className="text-sm font-bold mb-2">{tr("Trader Receivables Ledger", "வியாபாரி பாக்கி பேரேடு")}</h2>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">{tr("Trader", "வியாபாரி")}</th>
                  <th className="py-2 pr-3">{tr("Metres", "மீட்டர்")}</th>
                  <th className="py-2 pr-3">{tr("Billed", "பில் தொகை")}</th>
                  <th className="py-2 pr-3">{tr("Received", "வந்தது")}</th>
                  <th className="py-2 pr-3">{tr("Shortage Ded.", "குறைவு கழிவு")}</th>
                  <th className="py-2 pr-3">{tr("Rate-Cut Loss", "விலை குறைப்பு")}</th>
                  <th className="py-2">{tr("Balance Due", "மீதி பாக்கி")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ledger.map((l) => (
                  <tr key={l.trader_id}>
                    <td className="py-2 pr-3 font-bold">{l.company_name}</td>
                    <td className="py-2 pr-3">{l.total_metres} m</td>
                    <td className="py-2 pr-3">{formatRupeesFromPaise(l.billed_paise)}</td>
                    <td className="py-2 pr-3 text-emerald-700">{formatRupeesFromPaise(l.received_paise)}</td>
                    <td className="py-2 pr-3">{formatRupeesFromPaise(l.shortage_paise)}</td>
                    <td className="py-2 pr-3 text-rose-700">{formatRupeesFromPaise(l.underpayment_paise)}</td>
                    <td className="py-2 font-bold">{formatRupeesFromPaise(l.balance_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowPaymentForm((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold cursor-pointer transition ${
                showPaymentForm
                  ? "bg-slate-900 text-white"
                  : "bg-amber-500 text-slate-950 hover:bg-amber-400 shadow-sm"
              }`}
            >
              <Plus className="w-4 h-4" />
              {showPaymentForm ? tr("Close Payment Form", "வரவு படிவத்தை மூடு") : tr("Record Trader Payment", "வியாபாரி வரவு பதிவு")}
            </button>
          </div>

          {showPaymentForm && (
          <form onSubmit={submitPayment} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm grid sm:grid-cols-5 gap-2 items-end">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Trader *", "வியாபாரி *")}</label>
              <select
                required
                value={payTraderId}
                onChange={(e) => setPayTraderId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
              >
                {traders.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.company_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Payment Date *", "வரவு தேதி *")}</label>
              <input type="date" required value={payDate} onChange={(e) => setPayDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Received Amount (₹) *", "வந்த தொகை (₹) *")}</label>
              <input type="number" step="0.01" min="0.01" required placeholder="e.g. 5000" value={payAmtRs} onChange={(e) => setPayAmtRs(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Shortage Cut (₹, optional)", "குறைவு கழிவு (₹)")}</label>
              <input type="number" step="0.01" min="0" placeholder="0" value={payShortRs} onChange={(e) => setPayShortRs(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div className="flex gap-2 items-end">
              <div className="w-full">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Reference (optional)", "குறிப்பு (விருப்பம்)")}</label>
                <input placeholder="NEFT / UPI" value={payRef} onChange={(e) => setPayRef(e.target.value)} className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm" />
              </div>
              <button type="submit" disabled={submitting} className="px-3.5 py-2 rounded bg-slate-900 text-white text-xs font-semibold shrink-0 cursor-pointer disabled:opacity-50">{tr("Add", "சேர்")}</button>
            </div>
          </form>
          )}

          {payments.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
              {payments.map((p) => (
                <div key={p.id} className="px-4 py-2 text-xs flex justify-between items-center gap-2">
                  <span><b>{p.trader_name}</b> · {formatDateDMY(p.payment_date)} · {p.reference ?? "-"}</span>
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-emerald-700">{formatRupeesFromPaise(p.amount_paise)}</span>
                    <button
                      type="button"
                      onClick={() => void softDeleteRecord(`/payments/${p.id}`, `Payment #${p.id}`)}
                      className="text-rose-600 hover:underline inline-flex items-center gap-0.5"
                    >
                      <Trash2 className="w-3.5 h-3.5" /> {tr("Void", "நீக்கு")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Expenses */}
      {tab === "expenses" && (
        <div className="space-y-4">
          <div>
            <button
              type="button"
              onClick={() => setShowExpenseForm((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold cursor-pointer transition ${
                showExpenseForm
                  ? "bg-slate-900 text-white"
                  : "bg-amber-500 text-slate-950 hover:bg-amber-400 shadow-sm"
              }`}
            >
              <Plus className="w-4 h-4" />
              {showExpenseForm ? tr("Close Expense Form", "செலவு படிவத்தை மூடு") : tr("Add Shed Expense", "ஆலை செலவு சேர்")}
            </button>
          </div>
          {showExpenseForm && (
          <form onSubmit={submitExpense} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm grid sm:grid-cols-4 gap-2 items-end">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Expense Date *", "செலவு தேதி *")}</label>
              <input type="date" required value={expDate} onChange={(e) => setExpDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Category *", "வகை *")}</label>
              <input required value={expCategory} onChange={(e) => setExpCategory(e.target.value)} placeholder={tr("e.g. Loom Oil", "எ.கா. தறி எண்ணெய்")} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Amount (₹) *", "தொகை (₹) *")}</label>
              <input type="number" step="0.01" min="0.01" required value={expAmtRs} onChange={(e) => setExpAmtRs(e.target.value)} placeholder="e.g. 500" className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div className="flex gap-2 items-end">
              <div className="w-full">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Note (optional)", "குறிப்பு (விருப்பம்)")}</label>
                <input value={expNote} onChange={(e) => setExpNote(e.target.value)} placeholder={tr("Details", "விவரம்")} className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm" />
              </div>
              <button type="submit" disabled={submitting} className="px-3.5 py-2 rounded bg-slate-900 text-white text-xs font-semibold shrink-0 cursor-pointer disabled:opacity-50">{tr("Save", "சேமி")}</button>
            </div>
          </form>
          )}
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {expenses.map((e) => (
              <div key={e.id} className="px-4 py-2.5 text-xs flex justify-between items-center gap-2">
                <span><b>{e.category}</b> · {formatDateDMY(e.expense_date)} · {e.note ?? "-"}</span>
                <div className="flex items-center gap-3">
                  <span className="font-bold">{formatRupeesFromPaise(e.amount_paise)}</span>
                  <button
                    type="button"
                    onClick={() => void softDeleteRecord(`/expenses/${e.id}`, `Expense ${e.category}`)}
                    className="text-rose-600 hover:underline inline-flex items-center gap-0.5"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> {tr("Void", "நீக்கு")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: EB Meter Readings, Bills & CSV Backfill */}
      {tab === "eb" && (
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-amber-950 font-medium">
              {tr(
                "Want to verify a TNPDCL bill or estimate EB cost from fabric metres without saving?",
                "சேமிக்காமல் TNPDCL மின் கட்டணத்தை சரிபார்க்க அல்லது மீட்டருக்கு EB செலவைக் கணக்கிட வேண்டுமா?"
              )}
            </span>
            <Link
              to="/analytics?tab=eb"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold hover:bg-amber-400"
            >
              <Zap className="w-3.5 h-3.5" /> {tr("Open EB Bill Calculator →", "EB கணக்கீட்டாளரைத் திற →")}
            </Link>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <form onSubmit={submitEbReading} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-600" /> {tr("Log EB Meter Snapshot", "EB மீட்டர் ரீடிங் பதிவு")}
              </h2>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Reading Date *", "ரீடிங் தேதி *")}</label>
                  <input type="date" required value={readDate} onChange={(e) => setReadDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Meter Reading (kWh) *", "மீட்டர் எண் (kWh) *")}</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 15490" value={readKwh} onChange={(e) => setReadKwh(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
                </div>
              </div>
              <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer">{tr("Save Reading", "ரீடிங் சேமி")}</button>
              <div className="text-xs text-slate-600 space-y-1 pt-2">
                {ebReadings.slice(0, 5).map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2">
                    <span>{formatDateDMY(r.reading_date)}: <b>{r.kwh_total} kWh</b></span>
                    <button
                      type="button"
                      onClick={() => softDeleteRecord(`/eb-readings/${r.id}`, `EB Reading (${formatDateDMY(r.reading_date)})`)}
                      className="text-rose-600 hover:underline text-[11px] cursor-pointer"
                    >
                      {tr("Void", "நீக்கு")}
                    </button>
                  </div>
                ))}
              </div>
            </form>

            <form onSubmit={submitEbBill} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
              <h2 className="text-sm font-bold">{tr("Record Official Bi-Monthly EB Bill", "இரு மாத EB பில் பதிவு")}</h2>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Bill Period Start *", "பில் தொடக்க தேதி *")}</label>
                  <input type="date" required value={billStart} onChange={(e) => setBillStart(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Bill Period End *", "பில் முடிவு தேதி *")}</label>
                  <input type="date" required value={billEnd} onChange={(e) => setBillEnd(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Units (kWh) *", "யூனிட் (kWh) *")}</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 2150" value={billUnits} onChange={(e) => setBillUnits(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Net Bill (₹) *", "மொத்த பில் (₹) *")}</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 7560" value={billNetRs} onChange={(e) => setBillNetRs(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Power Cut (mins, opt.)", "மின்வெட்டு (நிமிடம்)")}</label>
                  <input type="number" min="0" placeholder="0" value={billPowerCutMins} onChange={(e) => setBillPowerCutMins(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
              </div>
              <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold cursor-pointer disabled:opacity-50">{tr("Save EB Bill", "EB பில் சேமி")}</button>
            </form>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <h3 className="text-sm font-bold flex items-center gap-1.5"><Upload className="w-4 h-4" /> {tr("Historical CSV Backfill", "பழைய CSV தரவு பதிவேற்றம்")}</h3>
            <div className="flex flex-wrap gap-4 text-xs">
              <label className="px-3 py-2 rounded-lg border border-slate-300 cursor-pointer hover:bg-slate-50">
                {tr("Import Historical EB Bills CSV", "பழைய EB பில் CSV பதிவேற்று")}
                <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && void uploadHistoryCsv("eb-bills-csv", e.target.files[0])} />
              </label>
              <label className="px-3 py-2 rounded-lg border border-slate-300 cursor-pointer hover:bg-slate-50">
                {tr("Import Weekly Deliveries CSV", "வாராந்திர டெலிவரி CSV பதிவேற்று")}
                <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && void uploadHistoryCsv("deliveries-csv", e.target.files[0])} />
              </label>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {ebBills.map((b) => (
              <div key={b.id} className="px-4 py-2.5 text-xs flex flex-wrap justify-between items-center gap-2">
                <span>
                  <b>{formatDateDMY(b.period_start)} – {formatDateDMY(b.period_end)}</b> · {b.units_consumed} kWh · {tr("Cut", "மின்வெட்டு")} {formatHoursFromMins(b.total_power_cut_mins)} hrs
                </span>
                <div className="flex items-center gap-3">
                  <span>
                    {tr("Energy", "மின் கட்டணம்")} {formatRupeesFromPaise(b.energy_paise)} + {tr("Fixed", "நிலை")} {formatRupeesFromPaise(b.fixed_paise)} + {tr("Tax", "வரி")}{" "}
                    {formatRupeesFromPaise(b.tax_paise)} = <b>{formatRupeesFromPaise(b.net_bill_paise)}</b>
                  </span>
                  <button
                    type="button"
                    onClick={() => void softDeleteRecord(`/eb-bills/${b.id}`, `EB Bill ${b.period_start}`)}
                    className="text-rose-600 hover:underline inline-flex items-center gap-0.5"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> {tr("Void", "நீக்கு")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 5: CSV Exports & Hot SQLite Backup */}
      {tab === "exports" && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <FileSpreadsheet className="w-4 h-4 text-emerald-700" /> {tr("Excel-Safe CSV Exports (UTF-8 BOM)", "எக்செல் CSV பதிவிறக்கம் (தமிழ் ஆதரவு)")}
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                ["shifts", tr("Shift Entries", "ஷிப்ட் பதிவுகள்")],
                ["beams", tr("Warp Beams", "பாவு பீம்கள்")],
                ["payslips", tr("Payslips", "சம்பள ரசீதுகள்")],
                ["advances", tr("Advances", "அட்வான்ஸ்")],
                ["deliveries", tr("Deliveries", "டெலிவரி")],
                ["expenses", tr("Expenses", "செலவுகள்")],
                ["eb_bills", tr("EB Bills", "EB பில்கள்")],
                ["eb_readings", tr("EB Readings", "EB ரீடிங்")],
                ["audit_logs", tr("Audit Log", "மாற்றப் பதிவு")],
              ].map(([entity, label]) => (
                <button
                  key={entity}
                  type="button"
                  onClick={() => void downloadProtectedFile(`/exports/csv/${entity}`, `loomos_${entity}.csv`)}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-left hover:bg-slate-50 inline-flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5 text-slate-600" /> {label}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <Database className="w-4 h-4 text-amber-600" /> {tr("Full SQLite Database Backup", "முழு தரவுத்தள பேக்கப் (.db)")}
            </h2>
            <p className="text-xs text-slate-600">
              {tr(
                "Downloads a transactionally consistent snapshot of your entire shed ledger using SQLite online backup API. Store copies weekly on Google Drive or a USB stick.",
                "உங்கள் முழு ஆலை கணக்கின் பாதுகாப்பான பேக்கப்பைப் பதிவிறக்கும். வாரந்தோறும் Google Drive அல்லது USB-இல் சேமித்து வைக்கவும்."
              )}
            </p>
            <button
              type="button"
              onClick={() => void downloadProtectedFile("/backup/sqlite", "loomos_backup.db")}
              className="px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-bold inline-flex items-center gap-2"
            >
              <Download className="w-4 h-4" /> {tr("Download Full Backup (.db)", "முழு பேக்கப் பதிவிறக்கு (.db)")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

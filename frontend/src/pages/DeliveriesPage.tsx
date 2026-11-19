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

  const selectedSort = sorts.find((s) => s.id === delSortId);
  const appliedPaisePreview = Math.round((parseFloat(delRateRs || "0") || 0) * 100);
  const hasInlineRateCut = selectedSort ? appliedPaisePreview > 0 && appliedPaisePreview < selectedSort.agreed_rate_paise : false;

  const submitDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
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
      setSuccess(
        res.has_rate_cut
          ? `Challan saved — RATE CUT DETECTED: shortfall ${formatRupeesFromPaise(res.total_underpayment_paise)}!`
          : "Delivery challan saved."
      );
      setChallanNo(suggestNextChallanNo([res, ...deliveries]));
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create delivery");
    }
  };

  const submitPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/payments", {
        method: "POST",
        body: JSON.stringify({
          trader_id: payTraderId,
          payment_date: payDate,
          amount_paise: Math.round(parseFloat(payAmtRs) * 100),
          shortage_deduction_paise: Math.round(parseFloat(payShortRs || "0") * 100),
          reference: payRef || null,
        }),
      });
      setPayAmtRs("");
      setPayRef("");
      setSuccess("Trader payment recorded.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save payment");
    }
  };

  const submitExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/expenses", {
        method: "POST",
        body: JSON.stringify({
          expense_date: expDate,
          category: expCategory,
          amount_paise: Math.round(parseFloat(expAmtRs) * 100),
          note: expNote || null,
        }),
      });
      setExpAmtRs("");
      setExpNote("");
      setSuccess("Expense saved.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save expense");
    }
  };

  const submitEbReading = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/eb-readings", {
        method: "POST",
        body: JSON.stringify({ reading_date: readDate, kwh_total: readKwh }),
      });
      setReadKwh("");
      setSuccess("EB meter snapshot saved.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save EB reading");
    }
  };

  const submitEbBill = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/eb-bills", {
        method: "POST",
        body: JSON.stringify({
          period_start: billStart,
          period_end: billEnd,
          units_consumed: billUnits,
          net_bill_paise: Math.round(parseFloat(billNetRs) * 100),
          total_power_cut_mins: Number(billPowerCutMins || "0"),
        }),
      });
      setBillUnits("");
      setBillNetRs("");
      setSuccess("EB bill saved and slab components reconciled.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save EB bill");
    }
  };

  const uploadHistoryCsv = async (kind: "eb-bills-csv" | "deliveries-csv", file: File) => {
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await apiRequest(`/imports/${kind}`, { method: "POST", body: fd });
      setSuccess(`Imported ${file.name} successfully.`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to import ${file.name}`);
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
      setSuccess(`Voided ${label} safely.`);
      await loadAll();
    } catch (err) {
      setVoidTarget(null);
      setError(err instanceof Error ? err.message : `Failed to void ${voidTarget.label}`);
    }
  };

  return (
    <div className="space-y-5">
      <ConfirmVoidModal
        open={Boolean(voidTarget)}
        title={`Void ${voidTarget?.label ?? ""}?`}
        description="Removes this record from totals and stores it in Change History."
        confirmLabel="Confirm Void"
        onCancel={() => setVoidTarget(null)}
        onConfirm={confirmSoftDelete}
      />
      <div>
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Truck className="w-5 h-5 text-amber-600" />
          Deliveries, Rate Checker, EB Ledger & Backups
        </h1>
        <p className="text-xs text-slate-500">
          Flags trader per-metre rate cuts automatically, tracks receivables, EB bills, and Excel-ready CSV/DB backups.
        </p>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      <PageGuideBanner
        tip="Record cloth deliveries (auto-checks if a trader cuts your per-metre rate), log money received, track shed expenses, and save EB meter snapshots or bills."
      />

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {[
          { id: "deliveries", label: `Deliveries & Rate Check (${deliveries.length})` },
          { id: "payments", label: "Trader Receivables & Payments" },
          { id: "expenses", label: `Expenses (${expenses.length})` },
          { id: "eb", label: `EB Readings & Bills (${ebBills.length})` },
          { id: "exports", label: "CSV Exports & DB Backup" },
        ].map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id as TabId)}
            className={`px-3 py-2 rounded-lg text-xs font-semibold ${
              tab === item.id ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
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
              {showDeliveryForm ? "Close Challan Form" : "Add Delivery Challan"}
            </button>
          </div>
          {showDeliveryForm && (
          <form onSubmit={submitDelivery} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm space-y-3">
            <div>
              <h2 className="text-sm font-bold">Record Cloth Delivery Challan (Rate Checker Active)</h2>
              <p className="text-[11px] text-slate-500">
                Challan No auto-fills next number (editable if copying a printed slip). Rate Checker compares Applied Rate vs Agreed Sort Rate and flags underpayments automatically.
              </p>
            </div>
            <div className="grid sm:grid-cols-4 gap-2">
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Trader *</label>
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
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Challan No (Auto / Editable) *</label>
                <input
                  required
                  placeholder="e.g. CH-203"
                  value={challanNo}
                  onChange={(e) => setChallanNo(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Delivery Date *</label>
                <input
                  type="date"
                  required
                  value={delDate}
                  onChange={(e) => setDelDate(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Warp Beam (optional)</label>
                <select
                  value={delBeamId}
                  onChange={(e) => setDelBeamId(e.target.value ? Number(e.target.value) : "")}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
                >
                  <option value="">None / Unlinked</option>
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
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Fabric Sort *</label>
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
                      {s.sort_name} (Agreed ₹{(s.agreed_rate_paise / 100).toFixed(2)})
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Pieces (Taakas)</label>
                <input
                  type="number"
                  min="1"
                  value={delPieces}
                  onChange={(e) => setDelPieces(e.target.value)}
                  className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Delivered Metres *</label>
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
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Applied Rate (₹/m) *</label>
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
                Rate cut warning: Applied ₹{delRateRs}/m is below agreed{" "}
                {formatRupeesFromPaise(selectedSort.agreed_rate_paise)}/m (shortfall ≈{" "}
                {formatRupeesFromPaise(
                  Math.round((selectedSort.agreed_rate_paise - appliedPaisePreview) * parseFloat(delMetres || "0"))
                )}
                ).
              </div>
            )}
            <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold cursor-pointer">
              Save Delivery Challan
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
                      RATE CUT: -{formatRupeesFromPaise(d.total_underpayment_paise)}
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
                    <Trash2 className="w-3.5 h-3.5" /> Void
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
            <h2 className="text-sm font-bold mb-2">Trader Receivables Ledger</h2>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Trader</th>
                  <th className="py-2 pr-3">Metres</th>
                  <th className="py-2 pr-3">Billed</th>
                  <th className="py-2 pr-3">Received</th>
                  <th className="py-2 pr-3">Shortage Ded.</th>
                  <th className="py-2 pr-3">Rate-Cut Loss</th>
                  <th className="py-2">Balance Due</th>
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
              {showPaymentForm ? "Close Payment Form" : "Record Trader Payment"}
            </button>
          </div>

          {showPaymentForm && (
          <form onSubmit={submitPayment} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm grid sm:grid-cols-5 gap-2 items-end">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Trader *</label>
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
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Payment Date *</label>
              <input type="date" required value={payDate} onChange={(e) => setPayDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Received Amount (₹) *</label>
              <input type="number" step="0.01" min="0.01" required placeholder="e.g. 5000" value={payAmtRs} onChange={(e) => setPayAmtRs(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Shortage Cut (₹, optional)</label>
              <input type="number" step="0.01" min="0" placeholder="0" value={payShortRs} onChange={(e) => setPayShortRs(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div className="flex gap-2 items-end">
              <div className="w-full">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Reference (optional)</label>
                <input placeholder="NEFT / UPI" value={payRef} onChange={(e) => setPayRef(e.target.value)} className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm" />
              </div>
              <button type="submit" className="px-3.5 py-2 rounded bg-slate-900 text-white text-xs font-semibold shrink-0 cursor-pointer">Add</button>
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
                      <Trash2 className="w-3.5 h-3.5" /> Void
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
              {showExpenseForm ? "Close Expense Form" : "Add Shed Expense"}
            </button>
          </div>
          {showExpenseForm && (
          <form onSubmit={submitExpense} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm grid sm:grid-cols-4 gap-2 items-end">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Expense Date *</label>
              <input type="date" required value={expDate} onChange={(e) => setExpDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Category *</label>
              <input required value={expCategory} onChange={(e) => setExpCategory(e.target.value)} placeholder="e.g. Loom Oil" className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Amount (₹) *</label>
              <input type="number" step="0.01" min="0.01" required value={expAmtRs} onChange={(e) => setExpAmtRs(e.target.value)} placeholder="e.g. 500" className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>
            <div className="flex gap-2 items-end">
              <div className="w-full">
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Note (optional)</label>
                <input value={expNote} onChange={(e) => setExpNote(e.target.value)} placeholder="Details" className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm" />
              </div>
              <button type="submit" className="px-3.5 py-2 rounded bg-slate-900 text-white text-xs font-semibold shrink-0 cursor-pointer">Save</button>
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
                    <Trash2 className="w-3.5 h-3.5" /> Void
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
              Want to verify a TNPDCL bill or estimate EB cost from fabric metres without saving?
            </span>
            <Link
              to="/analytics?tab=eb"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold hover:bg-amber-400"
            >
              <Zap className="w-3.5 h-3.5" /> Open EB Bill Calculator →
            </Link>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <form onSubmit={submitEbReading} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-600" /> Log EB Meter Snapshot
              </h2>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Reading Date *</label>
                  <input type="date" required value={readDate} onChange={(e) => setReadDate(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Meter Reading (kWh) *</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 15490" value={readKwh} onChange={(e) => setReadKwh(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm" />
                </div>
              </div>
              <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">Save Reading</button>
              <div className="text-xs text-slate-600 space-y-1 pt-2">
                {ebReadings.slice(0, 5).map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2">
                    <span>{formatDateDMY(r.reading_date)}: <b>{r.kwh_total} kWh</b></span>
                    <button
                      type="button"
                      onClick={() => softDeleteRecord(`/eb-readings/${r.id}`, `EB Reading (${formatDateDMY(r.reading_date)})`)}
                      className="text-rose-600 hover:underline text-[11px] cursor-pointer"
                    >
                      Void
                    </button>
                  </div>
                ))}
              </div>
            </form>

            <form onSubmit={submitEbBill} className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
              <h2 className="text-sm font-bold">Record Official Bi-Monthly EB Bill</h2>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Bill Period Start *</label>
                  <input type="date" required value={billStart} onChange={(e) => setBillStart(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Bill Period End *</label>
                  <input type="date" required value={billEnd} onChange={(e) => setBillEnd(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Units (kWh) *</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 2150" value={billUnits} onChange={(e) => setBillUnits(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Net Bill (₹) *</label>
                  <input type="number" step="0.01" min="0" required placeholder="e.g. 7560" value={billNetRs} onChange={(e) => setBillNetRs(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Power Cut (mins, optional)</label>
                  <input type="number" min="0" placeholder="0" value={billPowerCutMins} onChange={(e) => setBillPowerCutMins(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs" />
                </div>
              </div>
              <button type="submit" className="px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold">Save EB Bill</button>
            </form>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <h3 className="text-sm font-bold flex items-center gap-1.5"><Upload className="w-4 h-4" /> Historical CSV Backfill</h3>
            <div className="flex flex-wrap gap-4 text-xs">
              <label className="px-3 py-2 rounded-lg border border-slate-300 cursor-pointer hover:bg-slate-50">
                Import Historical EB Bills CSV
                <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && void uploadHistoryCsv("eb-bills-csv", e.target.files[0])} />
              </label>
              <label className="px-3 py-2 rounded-lg border border-slate-300 cursor-pointer hover:bg-slate-50">
                Import Weekly Deliveries CSV
                <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && void uploadHistoryCsv("deliveries-csv", e.target.files[0])} />
              </label>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {ebBills.map((b) => (
              <div key={b.id} className="px-4 py-2.5 text-xs flex flex-wrap justify-between items-center gap-2">
                <span>
                  <b>{formatDateDMY(b.period_start)} to {formatDateDMY(b.period_end)}</b> · {b.units_consumed} kWh · Cut {formatHoursFromMins(b.total_power_cut_mins)} hrs
                </span>
                <div className="flex items-center gap-3">
                  <span>
                    Energy {formatRupeesFromPaise(b.energy_paise)} + Fixed {formatRupeesFromPaise(b.fixed_paise)} + Tax{" "}
                    {formatRupeesFromPaise(b.tax_paise)} = <b>{formatRupeesFromPaise(b.net_bill_paise)}</b>
                  </span>
                  <button
                    type="button"
                    onClick={() => void softDeleteRecord(`/eb-bills/${b.id}`, `EB Bill ${b.period_start}`)}
                    className="text-rose-600 hover:underline inline-flex items-center gap-0.5"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Void
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
              <FileSpreadsheet className="w-4 h-4 text-emerald-700" /> Excel-Safe CSV Exports (UTF-8 BOM)
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                ["shifts", "Shift Entries"],
                ["beams", "Warp Beams"],
                ["payslips", "Payslips"],
                ["advances", "Advances"],
                ["deliveries", "Deliveries"],
                ["expenses", "Expenses"],
                ["eb_bills", "EB Bills"],
                ["eb_readings", "EB Readings"],
                ["audit_logs", "Audit Log"],
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
              <Database className="w-4 h-4 text-amber-600" /> Full SQLite Database Backup
            </h2>
            <p className="text-xs text-slate-600">
              Downloads a transactionally consistent snapshot of your entire shed ledger using SQLite online backup API.
              Store copies weekly on Google Drive or a USB stick.
            </p>
            <button
              type="button"
              onClick={() => void downloadProtectedFile("/backup/sqlite", "loomos_backup.db")}
              className="px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-bold inline-flex items-center gap-2"
            >
              <Download className="w-4 h-4" /> Download Full Backup (.db)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

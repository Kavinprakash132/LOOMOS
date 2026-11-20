import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRightLeft, Layers, PackagePlus, Plus, Trash2, Unplug } from "lucide-react";
import { apiRequest, formatDateDMY, localIsoDate } from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { useAuth } from "../context/AuthContext";
import { Beam, FabricSort, Loom, Trader, UnloadReason, WeftReceipt } from "../types/api";

export function BeamsPage() {
  const { tr } = useAuth();
  const [beams, setBeams] = useState<Beam[]>([]);
  const [receipts, setReceipts] = useState<WeftReceipt[]>([]);
  const [traders, setTraders] = useState<Trader[]>([]);
  const [sorts, setSorts] = useState<FabricSort[]>([]);
  const [looms, setLooms] = useState<Loom[]>([]);
  const [etaMap, setEtaMap] = useState<Record<number, { eta_date_p50: string; on_track: boolean }>>({});
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Receive beam form
  const [beamNo, setBeamNo] = useState("");
  const [traderId, setTraderId] = useState<number>(0);
  const [sortId, setSortId] = useState<number>(0);
  const [receivedDate, setReceivedDate] = useState(localIsoDate());
  const [warpLength, setWarpLength] = useState("1000");
  const [openingWoven, setOpeningWoven] = useState("0");
  const [tailWaste, setTailWaste] = useState("3");
  const [dueDate, setDueDate] = useState("");

  // Weft receipt form
  const [weftBeamId, setWeftBeamId] = useState<number>(0);
  const [weftDate, setWeftDate] = useState(localIsoDate());
  const [weftBags, setWeftBags] = useState("1");
  const [weftKg, setWeftKg] = useState("50.0");
  const [weftNote, setWeftNote] = useState("");

  // Load / Unload modals (inline per beam card)
  const [mountBeamId, setMountBeamId] = useState<number | null>(null);
  const [mountLoomId, setMountLoomId] = useState<number>(0);

  const [unloadBeamId, setUnloadBeamId] = useState<number | null>(null);
  const [unloadReason, setUnloadReason] = useState<UnloadReason>("COMPLETED");
  const [returnedWeftKg, setReturnedWeftKg] = useState("0");
  const [actualWasteM, setActualWasteM] = useState("");
  const [voidWeftTarget, setVoidWeftTarget] = useState<{ id: number; label: string } | null>(null);
  const [openDrawer, setOpenDrawer] = useState<"none" | "beam" | "weft">("none");
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [b, wr, tr, sr, lm, ov] = await Promise.all([
        apiRequest<Beam[]>("/beams"),
        apiRequest<WeftReceipt[]>("/weft-receipts"),
        apiRequest<Trader[]>("/traders"),
        apiRequest<FabricSort[]>("/fabric-sorts"),
        apiRequest<Loom[]>("/looms"),
        apiRequest<{ beam_etas: { beam_id: number; eta_date_p50: string; on_track: boolean }[] }>("/analytics/overview").catch(() => ({ beam_etas: [] })),
      ]);
      setBeams(b);
      setReceipts(wr);
      setTraders(tr);
      setSorts(sr);
      setLooms(lm);
      const map: Record<number, { eta_date_p50: string; on_track: boolean }> = {};
      for (const row of ov.beam_etas ?? []) map[row.beam_id] = row;
      setEtaMap(map);
      if (!traderId && tr[0]) setTraderId(tr[0].id);
      if (!sortId && sr[0]) setSortId(sr[0].id);
      if (!weftBeamId && b[0]) setWeftBeamId(b[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load beams");
    }
  }, [traderId, sortId, weftBeamId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const busyLoomIds = new Set(beams.filter((b) => b.active_loom_id).map((b) => b.active_loom_id!));
  const freeLooms = looms.filter((l) => l.status === "OPERATIONAL" && !busyLoomIds.has(l.id));

  const handleCreateBeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest("/beams", {
        method: "POST",
        body: JSON.stringify({
          beam_no: beamNo,
          trader_id: traderId,
          sort_id: sortId,
          received_date: receivedDate,
          warp_length_m: warpLength,
          opening_woven_m: openingWoven || "0",
          expected_tail_waste_m: tailWaste || "0",
          due_date: dueDate || null,
        }),
      });
      setBeamNo("");
      setOpeningWoven("0");
      setSuccess(tr("Warp beam added.", "பீம் சேர்க்கப்பட்டது."));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("Could not add beam", "பீமை சேர்க்க முடியவில்லை"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateWeft = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest("/weft-receipts", {
        method: "POST",
        body: JSON.stringify({
          beam_id: weftBeamId || null,
          received_date: weftDate,
          bags: Number(weftBags),
          net_weight_kg: weftKg,
          note: weftNote || null,
        }),
      });
      setWeftNote("");
      setSuccess(tr("Weft yarn receipt recorded and wastage rechecked.", "ஊடு நூல் வரவு சேமிக்கப்பட்டு கழிவு சரிபார்க்கப்பட்டது."));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("Could not save weft receipt", "நூல் வரவை சேமிக்க முடியவில்லை"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleMount = async (beamId: number) => {
    if (!mountLoomId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest(`/beams/${beamId}/load`, {
        method: "POST",
        body: JSON.stringify({ loom_id: mountLoomId }),
      });
      setMountBeamId(null);
      setSuccess(tr("Beam mounted on loom.", "தறியில் பீம் ஏற்றப்பட்டது."));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("Failed to mount beam", "பீம் ஏற்ற முடியவில்லை"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnload = async (beamId: number) => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest(`/beams/${beamId}/unload`, {
        method: "POST",
        body: JSON.stringify({
          unload_reason: unloadReason,
          returned_weft_kg: returnedWeftKg || "0",
          actual_waste_m: actualWasteM ? actualWasteM : null,
        }),
      });
      setUnloadBeamId(null);
      setSuccess(tr("Beam unloaded and weft wastage reconciled.", "பீம் இறக்கப்பட்டு நூல் கழிவு கணக்கிடப்பட்டது."));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : tr("Failed to unload beam", "பீம் இறக்க முடியவில்லை"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleVoidWeft = async (reason: string) => {
    if (!voidWeftTarget) return;
    setError(null);
    try {
      await apiRequest(`/weft-receipts/${voidWeftTarget.id}`, {
        method: "DELETE",
        body: JSON.stringify({ reason }),
      });
      const lbl = voidWeftTarget.label;
      setVoidWeftTarget(null);
      setSuccess(`Voided ${lbl} cleanly.`);
      await loadData();
    } catch (err) {
      setVoidWeftTarget(null);
      setError(err instanceof Error ? err.message : "Failed to void weft receipt");
    }
  };

  const visibleBeams = statusFilter === "ALL" ? beams : beams.filter((b) => b.status === statusFilter);
  const beamNoById = new Map(beams.map((b) => [b.id, b.beam_no]));

  const statusLabel = (st: string) => {
    if (st === "ALL") return tr("ALL", "அனைத்தும்");
    if (st === "RUNNING") return tr("RUNNING", "ஓடுகிறது");
    if (st === "IN_STOCK") return tr("IN STOCK", "இருப்பில்");
    if (st === "COMPLETED") return tr("COMPLETED", "முடிந்தது");
    return st;
  };

  return (
    <div className="space-y-6">
      <ConfirmVoidModal
        open={Boolean(voidWeftTarget)}
        title={tr(`Void ${voidWeftTarget?.label ?? ""}?`, `${voidWeftTarget?.label ?? ""} பதிவை நீக்கவா?`)}
        description={tr(
          "Removes this weft yarn receipt and recalculates wastage while keeping a Change History entry.",
          "இந்த ஊடை நூல் பதிவை நீக்கி வீண் கணக்கை மீண்டும் கணக்கிடும்; மாற்றப் பதிவில் வரலாறு இருக்கும்."
        )}
        confirmLabel={tr("Confirm Void", "நீக்குதலை உறுதி செய்")}
        onCancel={() => setVoidWeftTarget(null)}
        onConfirm={handleVoidWeft}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-5 h-5 text-amber-600" />
            {tr("Warp Beams, Loom Loading & Weft Yarn Wastage", "பாவு பீம்கள், தறி ஏற்றம் & ஊடை நூல் வீண் கணக்கு")}
          </h1>
          <p className="text-xs text-slate-500">
            {tr(
              "Warp Beam = main lengthwise yarn roll loaded onto a loom; Weft = cross-yarn cones woven across it. Tracks remaining cloth length & yarn wastage.",
              "பாவு பீம் = தறியில் ஏற்றும் நீள நூல் உருளை; ஊடை = குறுக்கு நூல் கோன்கள். மீதி துணி நீளம் மற்றும் நூல் வீணை கண்காணிக்கும்."
            )}
          </p>
        </div>
        <div className="flex gap-1.5 text-xs font-semibold">
          {["ALL", "RUNNING", "IN_STOCK", "COMPLETED"].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-lg border ${
                statusFilter === st ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-300"
              }`}
            >
              {statusLabel(st)}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      <PageGuideBanner
        steps={[
          tr("Receive Warp Beam from Trader", "வியாபாரியிடம் பீம் வரவு பதிவு"),
          tr("Load Beam onto a Free Loom", "காலி தறியில் பீம் ஏற்றவும்"),
          tr("Issue Weft Cones as Needed", "தேவைக்கேற்ப ஊடை நூல் வழங்கவும்"),
          tr("Unload Empty Beam to Check Yarn Waste", "பீம் முடிந்ததும் இறக்கி வீணை சரிபார்க்கவும்"),
        ]}
      />

      {/* Action Buttons to open forms only when needed */}
      <div className="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={() => setOpenDrawer((cur) => (cur === "beam" ? "none" : "beam"))}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold cursor-pointer transition ${
            openDrawer === "beam"
              ? "bg-slate-900 text-white"
              : "bg-amber-500 text-slate-950 hover:bg-amber-400 shadow-sm"
          }`}
        >
          <Plus className="w-4 h-4" />
          {openDrawer === "beam"
            ? tr("Close Warp Beam Form", "பீம் படிவத்தை மூடு")
            : tr("Receive New Warp Beam", "புதிய பாவு பீம் வரவு")}
        </button>
        <button
          type="button"
          onClick={() => setOpenDrawer((cur) => (cur === "weft" ? "none" : "weft"))}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer transition ${
            openDrawer === "weft"
              ? "bg-slate-900 text-white"
              : "bg-white border border-slate-300 text-slate-800 hover:bg-slate-50"
          }`}
        >
          <Plus className="w-4 h-4" />
          {openDrawer === "weft"
            ? tr("Close Weft Form", "ஊடை படிவத்தை மூடு")
            : tr("Issue Weft Yarn Cones", "ஊடை நூல் கோன் வழங்கல்")}
        </button>
      </div>

      {/* Summary Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">{tr("Active Warp Beams (On Looms)", "தறியில் ஓடும் பீம்கள்")}</div>
          <div className="text-xl font-bold">{beams.filter((b) => b.status === "RUNNING").length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">{tr("In Stock", "இருப்பில்")}</div>
          <div className="text-xl font-bold">{beams.filter((b) => b.status === "IN_STOCK").length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">{tr("Free Operational Looms", "காலியான தறிகள்")}</div>
          <div className="text-xl font-bold">{freeLooms.length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">{tr("Wastage Alerts", "வீண் எச்சரிக்கைகள்")}</div>
          <div className="text-xl font-bold text-rose-600">{beams.filter((b) => b.wastage_flagged).length}</div>
        </div>
      </div>

      {/* Collapsible Receive Warp Beam / Log Weft Yarn Forms */}
      {openDrawer !== "none" && (
        <div className="grid gap-4">
        {openDrawer === "beam" && (
        <form onSubmit={handleCreateBeam} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm space-y-3">
          <h2 className="text-sm font-bold flex items-center gap-1.5">
            <PackagePlus className="w-4 h-4 text-amber-600" />
            {tr("Receive New Warp Beam", "புதிய பாவு பீம் வரவு")}
          </h2>
          <div className="grid sm:grid-cols-3 gap-2.5">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Beam Number *", "பீம் எண் *")}</label>
              <input
                required
                placeholder="e.g. BM-106"
                value={beamNo}
                onChange={(e) => setBeamNo(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Trader *", "வியாபாரி *")}</label>
              <select
                required
                value={traderId}
                onChange={(e) => setTraderId(Number(e.target.value))}
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
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Fabric Sort *", "துணி வகை *")}</label>
              <select
                required
                value={sortId}
                onChange={(e) => setSortId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
              >
                {sorts.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.sort_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-2 gap-2.5">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Received Date *", "பெற்ற தேதி *")}</label>
              <input
                type="date"
                required
                value={receivedDate}
                onChange={(e) => setReceivedDate(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Warp Length (m) *", "பாவு நீளம் (மீ) *")}</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={warpLength}
                onChange={(e) => setWarpLength(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Already Woven (m)", "ஏற்கனவே நெய்தது (மீ)")}</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={openingWoven}
                onChange={(e) => setOpeningWoven(e.target.value)}
                title={tr("For half-woven beams already on looms at Day-1 launch", "ஏற்கனவே பாதியளவு ஓடிய பீம்களுக்கு")}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Tail Waste (m)", "கடைசி வீண் (மீ)")}</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={tailWaste}
                onChange={(e) => setTailWaste(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Target Due Date (optional)", "முடிக்க வேண்டிய தேதி (விருப்பம்)")}</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="px-2.5 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold cursor-pointer disabled:opacity-50">
              {tr("Add Warp Beam", "பீம் சேர்")}
            </button>
          </div>
        </form>
        )}

        {openDrawer === "weft" && (
        <form onSubmit={handleCreateWeft} className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm space-y-3">
          <h2 className="text-sm font-bold">{tr("Issue Weft Yarn Bags / Cones to Beam", "பீமுக்கு ஊடை நூல் மூட்டை / கோன் வழங்கல்")}</h2>
          <div className="grid sm:grid-cols-2 gap-2.5">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Target Warp Beam *", "பீம் *")}</label>
              <select
                value={weftBeamId}
                onChange={(e) => setWeftBeamId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
              >
                {beams.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.beam_no} · {b.sort_name} ({statusLabel(b.status)})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">{tr("Received Date *", "தேதி *")}</label>
              <input
                type="date"
                required
                value={weftDate}
                onChange={(e) => setWeftDate(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Bags", "மூட்டைகள்")}</label>
              <input
                type="number"
                min={1}
                required
                value={weftBags}
                onChange={(e) => setWeftBags(e.target.value)}
                className="w-full px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Net Weight (kg)", "நிகர எடை (கிலோ)")}</label>
              <input
                type="number"
                step="0.001"
                min="0.001"
                required
                value={weftKg}
                onChange={(e) => setWeftKg(e.target.value)}
                className="w-full px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-500 block">{tr("Note (optional)", "குறிப்பு (விருப்பம்)")}</label>
              <input
                value={weftNote}
                onChange={(e) => setWeftNote(e.target.value)}
                placeholder={tr("Lot / cone note", "லாட் / கோன் குறிப்பு")}
                className="w-full px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold cursor-pointer disabled:opacity-50">
            {tr("Save Weft Issue", "ஊடை பதிவை சேமி")}
          </button>
        </form>
        )}
        </div>
      )}

      {/* Beam List */}
      <div className="space-y-3">
        {visibleBeams.map((b) => (
          <div key={b.id} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-base text-slate-900">{b.beam_no}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      b.status === "RUNNING"
                        ? "bg-emerald-100 text-emerald-800"
                        : b.status === "COMPLETED"
                        ? "bg-slate-200 text-slate-700"
                        : "bg-blue-100 text-blue-800"
                    }`}
                  >
                    {statusLabel(b.status)}
                    {b.active_loom_number ? ` · ${b.active_loom_number}` : ""}
                  </span>
                  {b.wastage_flagged && (
                    <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 text-[11px] font-bold inline-flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> {tr("Weft Waste", "ஊடை வீண்")} {b.actual_wastage_pct}% &gt; {b.allowed_wastage_pct}%
                    </span>
                  )}
                  {b.due_date && (
                    <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-[11px] font-medium">
                      {tr("Due", "இலக்கு")}: {formatDateDMY(b.due_date)}
                    </span>
                  )}
                  {b.status === "RUNNING" && etaMap[b.id] && (
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                        etaMap[b.id].on_track ? "bg-emerald-50 text-emerald-800" : "bg-rose-100 text-rose-800"
                      }`}
                    >
                      ETA: {formatDateDMY(etaMap[b.id].eta_date_p50)} ({etaMap[b.id].on_track ? tr("On Track", "சரியான வேகம்") : tr("Late", "தாமதம்")})
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {b.trader_name} · {b.sort_name} · {tr("Received", "பெற்றது")} {formatDateDMY(b.received_date)}
                </div>
              </div>

              <div className="flex gap-2">
                {b.status === "IN_STOCK" && (
                  <button
                    type="button"
                    onClick={() => {
                      setMountBeamId(mountBeamId === b.id ? null : b.id);
                      if (freeLooms[0]) setMountLoomId(freeLooms[0].id);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold inline-flex items-center gap-1"
                  >
                    <ArrowRightLeft className="w-3.5 h-3.5" /> {tr("Load on Loom", "தறியில் ஏற்று")}
                  </button>
                )}
                {b.status === "RUNNING" && (
                  <button
                    type="button"
                    onClick={() => {
                      setUnloadBeamId(unloadBeamId === b.id ? null : b.id);
                      setReturnedWeftKg(b.returned_weft_kg);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold inline-flex items-center gap-1"
                  >
                    <Unplug className="w-3.5 h-3.5" /> {tr("Unload / Reconcile", "இறக்கு / கணக்கு முடி")}
                  </button>
                )}
              </div>
            </div>

            {/* Warp progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span>
                  {tr("Woven", "நெய்தது")}: <b>{b.woven_m} m</b> / {tr("Usable", "மொத்தம்")} {b.usable_total_m} m
                </span>
                <span>
                  {tr("Remaining", "மீதி")}: <b>{b.remaining_m} m</b> ({b.progress_pct}%)
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-amber-500" style={{ width: `${Math.min(100, b.progress_pct)}%` }} />
              </div>
            </div>

            {/* Weft metrics */}
            <div className="flex flex-wrap gap-4 text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2">
              <span>{tr("Weft Issued", "ஊடை வழங்கியது")}: <b>{b.weft_received_kg} kg</b></span>
              <span>{tr("Returned", "திருப்பியது")}: <b>{b.returned_weft_kg} kg</b></span>
              <span>{tr("Net Used", "பயன்பாடு")}: <b>{b.weft_consumed_kg} kg</b></span>
              <span>{tr("Expected for Woven Metres", "தேவையான எடை")}: <b>{b.expected_weft_kg} kg</b></span>
              {b.actual_wastage_pct !== null && (
                <span className={b.wastage_flagged ? "text-rose-700 font-bold" : "text-emerald-700 font-semibold"}>
                  {tr("Actual Waste", "உண்மை வீண்")}: {b.actual_wastage_pct}% ({tr("Limit", "வரம்பு")} {b.allowed_wastage_pct}%)
                </span>
              )}
            </div>

            {/* Inline Mount UI */}
            {mountBeamId === b.id && (
              <div className="pt-2 border-t border-slate-200 flex flex-wrap items-center gap-2">
                {freeLooms.length === 0 ? (
                  <span className="text-xs text-rose-700">{tr("No free operational looms available. Unload a loom first.", "காலி தறிகள் இல்லை. முதலில் ஒரு தறியிலிருந்து பீமை இறக்கவும்.")}</span>
                ) : (
                  <>
                    <select
                      value={mountLoomId}
                      onChange={(e) => setMountLoomId(Number(e.target.value))}
                      className="px-3 py-1.5 rounded border border-slate-300 text-xs"
                    >
                      {freeLooms.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.loom_number} ({l.loom_type}, {l.rated_rpm} RPM)
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleMount(b.id)}
                      className="px-3 py-1.5 rounded bg-emerald-700 text-white text-xs font-semibold"
                    >
                      {tr("Confirm Mount", "ஏற்றத்தை உறுதி செய்")}
                    </button>
                  </>
                )}
              </div>
            )}

            {/* Inline Unload & Weft Reconciliation UI */}
            {unloadBeamId === b.id && (
              <div className="pt-2 border-t border-slate-200 grid sm:grid-cols-4 gap-2 items-end">
                <div>
                  <label className="text-[11px] text-slate-500 block">{tr("Unload Reason", "இறக்கும் காரணம்")}</label>
                  <select
                    value={unloadReason}
                    onChange={(e) => setUnloadReason(e.target.value as UnloadReason)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs"
                  >
                    <option value="COMPLETED">{tr("Completed (Warp Finished)", "முடிந்தது (பாவு தீர்ந்தது)")}</option>
                    <option value="PARTIAL_UNLOAD">{tr("Partial Unload (Back to Stock)", "பாதியில் இறக்கம் (இருப்புக்கு)")}</option>
                    <option value="TRANSFER">{tr("Transfer to Another Loom", "வேறொரு தறிக்கு மாற்றம்")}</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 block">{tr("Returned Leftover Weft (kg)", "திருப்பிய மீதி ஊடை (கிலோ)")}</label>
                  <input
                    type="number"
                    step="0.001"
                    value={returnedWeftKg}
                    onChange={(e) => setReturnedWeftKg(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 block">{tr("Actual Tail Waste (m, optional)", "கடைசி வீண் (மீ, விருப்பம்)")}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={actualWasteM}
                    onChange={(e) => setActualWasteM(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => void handleUnload(b.id)}
                  className="px-3 py-1.5 rounded bg-slate-900 text-white text-xs font-semibold"
                >
                  {tr("Confirm Unload", "இறக்கத்தை உறுதி செய்")}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Recent Weft Receipts */}
      {receipts.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
          <h3 className="text-sm font-bold">{tr(`Recent Weft Receipts (${receipts.length})`, `சமீபத்திய ஊடை நூல் பதிவுகள் (${receipts.length})`)}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-1.5 pr-3">{tr("Date", "தேதி")}</th>
                  <th className="py-1.5 pr-3">{tr("Warp Beam", "பீம்")}</th>
                  <th className="py-1.5 pr-3">{tr("Bags", "மூட்டை")}</th>
                  <th className="py-1.5 pr-3">{tr("Net Weight (kg)", "எடை (கிலோ)")}</th>
                  <th className="py-1.5 pr-3">{tr("Note", "குறிப்பு")}</th>
                  <th className="py-1.5">{tr("Action", "செயல்")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {receipts.slice(0, 15).map((r) => {
                  const beamLabel = r.beam_id ? (beamNoById.get(r.beam_id) ?? `#${r.beam_id}`) : "-";
                  return (
                    <tr key={r.id}>
                      <td className="py-1.5 pr-3">{formatDateDMY(r.received_date)}</td>
                      <td className="py-1.5 pr-3 font-semibold">{beamLabel}</td>
                      <td className="py-1.5 pr-3">{r.bags}</td>
                      <td className="py-1.5 pr-3 font-semibold">{r.net_weight_kg} kg</td>
                      <td className="py-1.5 pr-3 text-slate-500">{r.note ?? "-"}</td>
                      <td className="py-1.5">
                        <button
                          type="button"
                          onClick={() =>
                            setVoidWeftTarget({
                              id: r.id,
                              label: `Weft ${r.net_weight_kg} kg (${beamLabel})`,
                            })
                          }
                          className="text-rose-600 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                        >
                          <Trash2 className="w-3 h-3" /> {tr("Void", "நீக்கு")}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

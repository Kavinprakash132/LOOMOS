import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowRightLeft, Layers, PackagePlus, Trash2, Unplug } from "lucide-react";
import { apiRequest, formatDateDMY, localIsoDate } from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { Beam, FabricSort, Loom, Trader, UnloadReason, WeftReceipt } from "../types/api";

export function BeamsPage() {
  const [beams, setBeams] = useState<Beam[]>([]);
  const [receipts, setReceipts] = useState<WeftReceipt[]>([]);
  const [traders, setTraders] = useState<Trader[]>([]);
  const [sorts, setSorts] = useState<FabricSort[]>([]);
  const [looms, setLooms] = useState<Loom[]>([]);
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

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [b, wr, tr, sr, lm] = await Promise.all([
        apiRequest<Beam[]>("/beams"),
        apiRequest<WeftReceipt[]>("/weft-receipts"),
        apiRequest<Trader[]>("/traders"),
        apiRequest<FabricSort[]>("/fabric-sorts"),
        apiRequest<Loom[]>("/looms"),
      ]);
      setBeams(b);
      setReceipts(wr);
      setTraders(tr);
      setSorts(sr);
      setLooms(lm);
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
      setSuccess("Warp beam added.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add beam");
    }
  };

  const handleCreateWeft = async (e: React.FormEvent) => {
    e.preventDefault();
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
      setSuccess("Weft yarn receipt recorded and wastage rechecked.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save weft receipt");
    }
  };

  const handleMount = async (beamId: number) => {
    if (!mountLoomId) return;
    setError(null);
    try {
      await apiRequest(`/beams/${beamId}/load`, {
        method: "POST",
        body: JSON.stringify({ loom_id: mountLoomId }),
      });
      setMountBeamId(null);
      setSuccess("Beam mounted on loom.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mount beam");
    }
  };

  const handleUnload = async (beamId: number) => {
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
      setSuccess("Beam unloaded and weft wastage reconciled.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unload beam");
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

  return (
    <div className="space-y-6">
      <ConfirmVoidModal
        open={Boolean(voidWeftTarget)}
        title={`Void ${voidWeftTarget?.label ?? ""}?`}
        description="Removes this weft yarn receipt and recalculates wastage while keeping a Change History entry."
        confirmLabel="Confirm Void"
        onCancel={() => setVoidWeftTarget(null)}
        onConfirm={handleVoidWeft}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-5 h-5 text-amber-600" />
            Warp Beams, Loom Loading & Weft Yarn Wastage
          </h1>
          <p className="text-xs text-slate-500">
            Warp Beam = main lengthwise yarn roll loaded onto a loom; Weft = cross-yarn cones woven across it. Tracks remaining cloth length &amp; yarn wastage.
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
              {st}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      {/* Summary Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Active Warp Beams (On Looms)</div>
          <div className="text-xl font-bold">{beams.filter((b) => b.status === "RUNNING").length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">In Stock</div>
          <div className="text-xl font-bold">{beams.filter((b) => b.status === "IN_STOCK").length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Free Operational Looms</div>
          <div className="text-xl font-bold">{freeLooms.length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Wastage Alerts</div>
          <div className="text-xl font-bold text-rose-600">{beams.filter((b) => b.wastage_flagged).length}</div>
        </div>
      </div>

      {/* Receive Warp Beam + Log Weft Yarn Forms */}
      <div className="grid lg:grid-cols-2 gap-4">
        <form onSubmit={handleCreateBeam} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h2 className="text-sm font-bold flex items-center gap-1.5">
            <PackagePlus className="w-4 h-4 text-amber-600" />
            Receive New Warp Beam
          </h2>
          <div className="grid sm:grid-cols-3 gap-2.5">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Beam Number *</label>
              <input
                required
                placeholder="e.g. BM-106"
                value={beamNo}
                onChange={(e) => setBeamNo(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Trader *</label>
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
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Fabric Sort *</label>
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
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Received Date *</label>
              <input
                type="date"
                required
                value={receivedDate}
                onChange={(e) => setReceivedDate(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Warp Length (m) *</label>
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
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Already Woven (m)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={openingWoven}
                onChange={(e) => setOpeningWoven(e.target.value)}
                title="For half-woven beams already on looms at Day-1 launch"
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Tail Waste (m)</label>
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
              <label className="text-[11px] text-slate-500 block">Target Due Date (optional)</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="px-2.5 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
            <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
              Add Warp Beam
            </button>
          </div>
        </form>

        <form onSubmit={handleCreateWeft} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h2 className="text-sm font-bold">Issue Weft Yarn Bags / Cones to Beam</h2>
          <div className="grid sm:grid-cols-2 gap-2.5">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Target Warp Beam *</label>
              <select
                value={weftBeamId}
                onChange={(e) => setWeftBeamId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
              >
                {beams.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.beam_no} · {b.sort_name} ({b.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Received Date *</label>
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
              <label className="text-[11px] text-slate-500 block">Bags</label>
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
              <label className="text-[11px] text-slate-500 block">Net Weight (kg)</label>
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
              <label className="text-[11px] text-slate-500 block">Note (optional)</label>
              <input
                value={weftNote}
                onChange={(e) => setWeftNote(e.target.value)}
                placeholder="Lot / cone note"
                className="w-full px-3 py-1.5 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-semibold">
            Save Weft Issue
          </button>
        </form>
      </div>

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
                    {b.status}
                    {b.active_loom_number ? ` on ${b.active_loom_number}` : ""}
                  </span>
                  {b.wastage_flagged && (
                    <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 text-[11px] font-bold inline-flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Weft Waste {b.actual_wastage_pct}% &gt; {b.allowed_wastage_pct}%
                    </span>
                  )}
                  {b.due_date && (
                    <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-[11px] font-medium">
                      Due: {formatDateDMY(b.due_date)}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {b.trader_name} · {b.sort_name} · Received {formatDateDMY(b.received_date)}
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
                    <ArrowRightLeft className="w-3.5 h-3.5" /> Load on Loom
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
                    <Unplug className="w-3.5 h-3.5" /> Unload / Reconcile
                  </button>
                )}
              </div>
            </div>

            {/* Warp progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span>
                  Woven: <b>{b.woven_m} m</b> / Usable {b.usable_total_m} m
                </span>
                <span>
                  Remaining: <b>{b.remaining_m} m</b> ({b.progress_pct}%)
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full bg-amber-500" style={{ width: `${Math.min(100, b.progress_pct)}%` }} />
              </div>
            </div>

            {/* Weft metrics */}
            <div className="flex flex-wrap gap-4 text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2">
              <span>Weft Issued: <b>{b.weft_received_kg} kg</b></span>
              <span>Returned: <b>{b.returned_weft_kg} kg</b></span>
              <span>Net Used: <b>{b.weft_consumed_kg} kg</b></span>
              <span>Expected for Woven Metres: <b>{b.expected_weft_kg} kg</b></span>
              {b.actual_wastage_pct !== null && (
                <span className={b.wastage_flagged ? "text-rose-700 font-bold" : "text-emerald-700 font-semibold"}>
                  Actual Waste: {b.actual_wastage_pct}% (Limit {b.allowed_wastage_pct}%)
                </span>
              )}
            </div>

            {/* Inline Mount UI */}
            {mountBeamId === b.id && (
              <div className="pt-2 border-t border-slate-200 flex flex-wrap items-center gap-2">
                {freeLooms.length === 0 ? (
                  <span className="text-xs text-rose-700">No free operational looms available. Unload a loom first.</span>
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
                      Confirm Mount
                    </button>
                  </>
                )}
              </div>
            )}

            {/* Inline Unload & Weft Reconciliation UI */}
            {unloadBeamId === b.id && (
              <div className="pt-2 border-t border-slate-200 grid sm:grid-cols-4 gap-2 items-end">
                <div>
                  <label className="text-[11px] text-slate-500 block">Unload Reason</label>
                  <select
                    value={unloadReason}
                    onChange={(e) => setUnloadReason(e.target.value as UnloadReason)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs"
                  >
                    <option value="COMPLETED">Completed (Warp Finished)</option>
                    <option value="PARTIAL_UNLOAD">Partial Unload (Back to Stock)</option>
                    <option value="TRANSFER">Transfer to Another Loom</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 block">Returned Leftover Weft (kg)</label>
                  <input
                    type="number"
                    step="0.001"
                    value={returnedWeftKg}
                    onChange={(e) => setReturnedWeftKg(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500 block">Actual Tail Waste (m, optional)</label>
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
                  Confirm Unload
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Recent Weft Receipts */}
      {receipts.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
          <h3 className="text-sm font-bold">Recent Weft Receipts ({receipts.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-1.5 pr-3">Date</th>
                  <th className="py-1.5 pr-3">Warp Beam</th>
                  <th className="py-1.5 pr-3">Bags</th>
                  <th className="py-1.5 pr-3">Net Weight (kg)</th>
                  <th className="py-1.5 pr-3">Note</th>
                  <th className="py-1.5">Action</th>
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
                          <Trash2 className="w-3 h-3" /> Void
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

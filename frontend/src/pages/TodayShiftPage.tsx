import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, Calendar, ClipboardCheck, Plus, Save, Trash2, Users, X } from "lucide-react";
import { apiRequest, formatDateDMY, generateUuid, localIsoDate, offsetLocalIsoDate } from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { useAuth } from "../context/AuthContext";
import {
  AlertItem,
  AttendanceRecord,
  AttendanceStatus,
  Beam,
  CalendarDay,
  EntryMode,
  ShiftPrefillResponse,
  Weaver,
} from "../types/api";

interface EditableShiftRow {
  rowKey: string;
  existingId?: number;
  clientUuid: string;
  loomId: number;
  loomNumber: string;
  loomType: string;
  ratedRpm: number;
  activeSortName: string | null;
  remainingBeamM: string | null;
  weaverId: number;
  beamId: number | null;
  entryMode: EntryMode;
  startMeter: string;
  endMeter: string;
  netMetres: string;
  plannedMins: number;
  powerCutMins: number;
  downtimeMins: number;
  defectiveMetres: string;
  stopReasonId: number | null;
  notes: string;
  isSwapExtra?: boolean;
}

export function TodayShiftPage() {
  const { user } = useAuth();
  const isOwner = user?.role === "OWNER";
  const [entryDate, setEntryDate] = useState(localIsoDate());
  const [shiftNo, setShiftNo] = useState<number>(1);
  const [prefill, setPrefill] = useState<ShiftPrefillResponse | null>(null);
  const [rows, setRows] = useState<EditableShiftRow[]>([]);
  const [weavers, setWeavers] = useState<Weaver[]>([]);
  const [beams, setBeams] = useState<Beam[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [attemptedSave, setAttemptedSave] = useState(false);
  const [voidTarget, setVoidTarget] = useState<{ shiftId: number; loomNumber: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Worker attendance & Holiday panel state
  const [showAttendance, setShowAttendance] = useState(false);
  const [attMap, setAttMap] = useState<Record<number, AttendanceStatus>>({});
  const [isWorkingDay, setIsWorkingDay] = useState(true);
  const [calNote, setCalNote] = useState("");
  const [initializedShiftAuto, setInitializedShiftAuto] = useState(false);

  const loadMastersAndPrefill = useCallback(
    async (targetDate: string, targetShift: number | null) => {
      setError(null);
      try {
        const qs = targetShift
          ? `/shifts/prefill?entry_date=${targetDate}&shift_no=${targetShift}`
          : `/shifts/prefill?entry_date=${targetDate}`;
        const [pf, wv, bm, al, att, cal] = await Promise.all([
          apiRequest<ShiftPrefillResponse>(qs),
          apiRequest<Weaver[]>("/weavers"),
          apiRequest<Beam[]>("/beams"),
          apiRequest<AlertItem[]>("/alerts?status=OPEN"),
          apiRequest<AttendanceRecord[]>(`/attendance?from_date=${targetDate}&to_date=${targetDate}`),
          apiRequest<CalendarDay[]>(`/calendar?from_date=${targetDate}&to_date=${targetDate}`),
        ]);

        setPrefill(pf);
        if (!targetShift) setShiftNo(pf.shift_no);
        setWeavers(wv);
        setBeams(bm);
        setAlerts(al);

        const defaultWeaverId = wv[0]?.id ?? 0;
        const builtRows: EditableShiftRow[] = [];

        for (const lr of pf.looms) {
          if (lr.existing_entries.length > 0) {
            for (const ex of lr.existing_entries) {
              builtRows.push({
                rowKey: `${lr.loom_id}-${ex.id}`,
                existingId: ex.id,
                clientUuid: ex.client_uuid,
                loomId: lr.loom_id,
                loomNumber: lr.loom_number,
                loomType: lr.loom_type,
                ratedRpm: lr.rated_rpm,
                activeSortName: lr.active_sort_name,
                remainingBeamM: lr.remaining_beam_m,
                weaverId: ex.weaver_id,
                beamId: ex.beam_id,
                entryMode: ex.entry_mode,
                startMeter: ex.start_meter ?? "",
                endMeter: ex.end_meter ?? "",
                netMetres: ex.net_metres,
                plannedMins: ex.planned_mins,
                powerCutMins: ex.power_cut_mins,
                downtimeMins: ex.downtime_mins,
                defectiveMetres: ex.defective_metres,
                stopReasonId: ex.stop_reason_id,
                notes: ex.notes ?? "",
              });
            }
          } else {
            builtRows.push({
              rowKey: `${lr.loom_id}-new`,
              clientUuid: generateUuid(),
              loomId: lr.loom_id,
              loomNumber: lr.loom_number,
              loomType: lr.loom_type,
              ratedRpm: lr.rated_rpm,
              activeSortName: lr.active_sort_name,
              remainingBeamM: lr.remaining_beam_m,
              weaverId: lr.default_weaver_id ?? defaultWeaverId,
              beamId: lr.active_beam_id,
              entryMode: pf.default_entry_mode,
              startMeter: lr.last_end_meter ?? "",
              endMeter: "",
              netMetres: "",
              plannedMins: pf.planned_shift_mins,
              powerCutMins: 0,
              downtimeMins: 0,
              defectiveMetres: "0",
              stopReasonId: null,
              notes: "",
            });
          }
        }
        setRows(builtRows);

        const activeShift = targetShift ?? pf.suggested_shift;
        const map: Record<number, AttendanceStatus> = {};
        for (const a of att) {
          if (a.shift_no === activeShift) map[a.weaver_id] = a.status;
        }
        setAttMap(map);

        if (cal[0]) {
          setIsWorkingDay(cal[0].is_working_day);
          setCalNote(cal[0].note ?? "");
        } else {
          setIsWorkingDay(true);
          setCalNote("");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load shift grid");
      }
    },
    []
  );

  useEffect(() => {
    if (!initializedShiftAuto) {
      setInitializedShiftAuto(true);
      void loadMastersAndPrefill(entryDate, null);
    }
  }, [initializedShiftAuto, entryDate, loadMastersAndPrefill]);

  const handleDateOrShiftChange = (nextDate: string, nextShift: number) => {
    setEntryDate(nextDate);
    setShiftNo(nextShift);
    setAttemptedSave(false);
    setSuccess(null);
    void loadMastersAndPrefill(nextDate, nextShift);
  };

  const updateRow = (rowKey: string, patch: Partial<EditableShiftRow>) => {
    setRows((prev) =>
      prev.map((r) => {
        if (r.rowKey !== rowKey) return r;
        const next = { ...r, ...patch };
        if (next.entryMode === "COUNTER") {
          if (next.startMeter !== "" && next.endMeter !== "") {
            const diff = parseFloat(next.endMeter) - parseFloat(next.startMeter);
            next.netMetres = !Number.isNaN(diff) && diff >= 0 ? diff.toFixed(2) : "";
          } else {
            next.netMetres = "";
          }
        }
        return next;
      })
    );
  };

  const addBeamSwapRow = (src: EditableShiftRow) => {
    if (rows.some((x) => x.loomId === src.loomId && x.isSwapExtra)) return;
    const newRow: EditableShiftRow = {
      ...src,
      rowKey: `${src.loomId}-swap-${Date.now()}`,
      existingId: undefined,
      clientUuid: generateUuid(),
      beamId: null,
      netMetres: "",
      startMeter: src.endMeter || src.startMeter,
      endMeter: "",
      powerCutMins: 0,
      downtimeMins: 0,
      defectiveMetres: "0",
      isSwapExtra: true,
    };
    setRows((prev) => {
      const idx = prev.findIndex((x) => x.rowKey === src.rowKey);
      const copy = [...prev];
      copy.splice(idx + 1, 0, newRow);
      return copy;
    });
  };

  const removeSwapRow = (rowKey: string) => {
    setRows((prev) => prev.filter((r) => r.rowKey !== rowKey));
  };

  const isRowStopped = (r: EditableShiftRow) => r.downtimeMins >= r.plannedMins;

  const toggleRowStatus = (r: EditableShiftRow, stop: boolean) => {
    if (stop) {
      updateRow(r.rowKey, {
        downtimeMins: r.plannedMins,
        powerCutMins: 0,
        netMetres: "0",
        endMeter: r.entryMode === "COUNTER" && r.startMeter !== "" ? r.startMeter : r.endMeter,
      });
    } else {
      updateRow(r.rowKey, {
        downtimeMins: 0,
        powerCutMins: 0,
        netMetres: r.netMetres === "0" ? "" : r.netMetres,
      });
    }
  };

  const isRowCounterBad = (r: EditableShiftRow) => {
    if (r.entryMode !== "COUNTER") return false;
    const hasStart = r.startMeter !== "";
    const hasEnd = r.endMeter !== "";
    if (hasStart !== hasEnd) return true;
    return hasStart && hasEnd && parseFloat(r.endMeter) < parseFloat(r.startMeter);
  };

  const isRowDirectBad = (r: EditableShiftRow) =>
    r.entryMode === "DIRECT" && r.netMetres !== "" && parseFloat(r.netMetres) < 0;

  const isRowDefectBad = (r: EditableShiftRow) =>
    r.defectiveMetres !== "" && parseFloat(r.defectiveMetres) < 0;

  const hasValidMetresRow = rows.some((r) => {
    if (isRowStopped(r)) return true;
    if (r.entryMode === "COUNTER") {
      return r.startMeter !== "" && r.endMeter !== "" && parseFloat(r.endMeter) >= parseFloat(r.startMeter);
    }
    return r.netMetres !== "" && parseFloat(r.netMetres) >= 0;
  });

  const handleSaveGrid = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttemptedSave(true);
    setError(null);
    setSuccess(null);
    if (rows.some((r) => isRowCounterBad(r) || isRowDirectBad(r) || isRowDefectBad(r))) {
      setError("Fix the highlighted invalid shift fields before saving.");
      return;
    }
    const validRows = rows.filter((r) => {
      if (isRowStopped(r)) return true;
      if (r.entryMode === "COUNTER") return r.startMeter !== "" && r.endMeter !== "";
      return r.netMetres !== "";
    });
    if (validRows.length === 0) {
      setError("Enter metres (or mark a loom Stopped) before saving.");
      return;
    }
    if (weavers.length === 0) {
      setError("Add at least one Weaver in Settings before logging shifts.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        entry_date: entryDate,
        shift_no: shiftNo,
        rows: validRows.map((r) => ({
          client_uuid: r.clientUuid,
          loom_id: r.loomId,
          weaver_id: r.weaverId,
          beam_id: r.beamId,
          entry_mode: r.entryMode,
          start_meter: r.entryMode === "COUNTER" ? r.startMeter : null,
          end_meter: r.entryMode === "COUNTER" ? r.endMeter : null,
          net_metres: r.netMetres || "0",
          planned_mins: r.plannedMins,
          power_cut_mins: 0,
          downtime_mins: isRowStopped(r) ? r.plannedMins : 0,
          defective_metres: r.defectiveMetres || "0",
          stop_reason_id: r.stopReasonId,
          notes: r.notes || null,
        })),
      };
      const saved = await apiRequest<unknown[]>("/shifts/batch", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setAttemptedSave(false);
      setSuccess(`Saved ${saved.length} loom entries for ${formatDateDMY(entryDate)} (Shift ${shiftNo}).`);
      await loadMastersAndPrefill(entryDate, shiftNo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save shift entries");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAttendance = async () => {
    const items = Object.entries(attMap).map(([wid, st]) => ({
      weaver_id: Number(wid),
      status: st,
    }));
    if (items.length === 0) return;
    setError(null);
    try {
      await apiRequest("/attendance/batch", {
        method: "POST",
        body: JSON.stringify({ attendance_date: entryDate, shift_no: shiftNo, items }),
      });
      setSuccess(`Attendance saved for Shift ${shiftNo} (${items.length} workers).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save attendance");
    }
  };

  const handleSaveCalendar = async () => {
    setError(null);
    try {
      await apiRequest(`/calendar/${entryDate}`, {
        method: "PUT",
        body: JSON.stringify({
          is_working_day: isWorkingDay,
          planned_shifts: isWorkingDay ? (prefill?.shifts_per_day ?? 2) : 0,
          note: calNote || null,
        }),
      });
      setSuccess(`Shed calendar updated for ${formatDateDMY(entryDate)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update calendar");
    }
  };

  const dismissAlert = async (alertId: number) => {
    await apiRequest(`/alerts/${alertId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "DISMISSED" }),
    });
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  };

  const confirmVoidShift = async (reason: string) => {
    if (!voidTarget) return;
    setError(null);
    try {
      await apiRequest(`/shifts/${voidTarget.shiftId}`, {
        method: "DELETE",
        body: JSON.stringify({ reason }),
      });
      const clearedNum = voidTarget.loomNumber;
      setVoidTarget(null);
      setSuccess(`Removed saved shift entry for ${clearedNum} cleanly.`);
      await loadMastersAndPrefill(entryDate, shiftNo);
    } catch (err) {
      setVoidTarget(null);
      setError(err instanceof Error ? err.message : "Failed to remove shift");
    }
  };

  const maxShifts = prefill?.shifts_per_day ?? 2;
  const totalMetresEntered = rows.reduce((acc, r) => acc + (parseFloat(r.netMetres || "0") || 0), 0);

  return (
    <div className="space-y-5 pb-12">
      <ConfirmVoidModal
        open={Boolean(voidTarget)}
        title={`Remove Saved Shift on ${voidTarget?.loomNumber ?? ""}?`}
        description="This removes the saved production entry for this shift while keeping an audit record."
        confirmLabel="Remove Shift Entry"
        onCancel={() => setVoidTarget(null)}
        onConfirm={confirmVoidShift}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-amber-600" />
            Daily Shift Production Grid
          </h1>
          <p className="text-xs text-slate-500">
            Enter daily shuttle loom output, toggle Running / Stopped, and log mid-shift beam changes if needed.
          </p>
        </div>
        <div className="bg-slate-900 text-white px-3.5 py-2 rounded-xl text-xs font-semibold">
          Grid Total: <span className="text-amber-400 text-sm">{totalMetresEntered.toFixed(1)} m</span>
        </div>
      </div>

      {/* Open Alerts Banner */}
      {alerts.length > 0 && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 space-y-1.5">
          <div className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" /> Open Shed Alerts ({alerts.length})
          </div>
          {alerts.slice(0, 4).map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-2 text-xs text-amber-900">
              <span>
                <b>[{a.alert_type}]</b> {a.message}
              </span>
              <button
                type="button"
                onClick={() => void dismissAlert(a.id)}
                className="text-slate-600 underline shrink-0"
              >
                Dismiss
              </button>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      <PageGuideBanner
        steps={[
          "Pick Date & Shift (Day / Night)",
          "Type Metres Woven (or switch to Counter for Start→End)",
          "Mark any Stopped loom & click Save Shift",
        ]}
      />

      {/* Smart Date & Shift Bar */}
      <div className="bg-white p-3.5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleDateOrShiftChange(localIsoDate(), shiftNo)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              entryDate === localIsoDate()
                ? "bg-amber-500 text-slate-950 border-amber-500"
                : "bg-white text-slate-700 border-slate-300"
            }`}
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => handleDateOrShiftChange(offsetLocalIsoDate(-1), shiftNo)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
              entryDate === offsetLocalIsoDate(-1)
                ? "bg-amber-500 text-slate-950 border-amber-500"
                : "bg-white text-slate-700 border-slate-300"
            }`}
          >
            Yesterday
          </button>
          <input
            type="date"
            value={entryDate}
            onChange={(e) => handleDateOrShiftChange(e.target.value, shiftNo)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 text-sm font-medium"
          />
          <div className="inline-flex rounded-lg border border-slate-300 bg-slate-100 p-0.5 text-xs font-semibold">
            {[
              { no: 1, label: "Shift 1 (Day)" },
              ...(maxShifts >= 2 ? [{ no: 2, label: "Shift 2 (Night)" }] : []),
              ...(maxShifts >= 3 ? [{ no: 3, label: "Shift 3" }] : []),
            ].map((s) => (
              <button
                key={s.no}
                type="button"
                onClick={() => handleDateOrShiftChange(entryDate, s.no)}
                className={`px-3 py-1.5 rounded-md cursor-pointer transition ${
                  shiftNo === s.no ? "bg-slate-900 text-white shadow-xs" : "text-slate-700 hover:text-slate-900"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAttendance((v) => !v)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold inline-flex items-center gap-1.5 hover:bg-slate-50"
          >
            <Users className="w-3.5 h-3.5" /> Worker Attendance &amp; Holiday
          </button>
          <div className="inline-flex items-center rounded-lg border border-slate-300 bg-slate-50 p-0.5 text-xs">
            <span className="px-2 text-[11px] font-semibold text-slate-500">All Looms:</span>
            <button
              type="button"
              onClick={() => setRows((prev) => prev.map((r) => ({ ...r, entryMode: "DIRECT" })))}
              className="px-2.5 py-1 rounded-md font-semibold bg-white hover:bg-slate-100 text-slate-800 shadow-xs cursor-pointer"
              title="Type total cloth metres directly"
            >
              Total Metres
            </button>
            <button
              type="button"
              onClick={() => setRows((prev) => prev.map((r) => ({ ...r, entryMode: "COUNTER" })))}
              className="px-2.5 py-1 rounded-md font-semibold text-slate-700 hover:bg-white cursor-pointer"
              title="Enter Start & End loom meter readings"
            >
              Meter Counter
            </button>
          </div>
        </div>
      </div>

      {/* Collapsible Attendance & Holiday Panel */}
      {showAttendance && (
        <div className="grid md:grid-cols-2 gap-4 bg-white p-4 rounded-xl border border-slate-200">
          <div className="space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <Users className="w-4 h-4 text-amber-600" />
              Shift {shiftNo} Attendance (Helpers, Fitters & Zero-Loom Weavers)
            </h2>
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {weavers.map((w) => (
                <div key={w.id} className="flex items-center justify-between gap-2 text-xs bg-slate-50 px-2.5 py-1.5 rounded">
                  <span>
                    <b>{w.full_name}</b> <span className="text-slate-500">({w.role_type})</span>
                  </span>
                  <select
                    value={attMap[w.id] ?? ""}
                    onChange={(e) => {
                      const val = e.target.value as AttendanceStatus | "";
                      setAttMap((prev) => {
                        const copy = { ...prev };
                        if (!val) delete copy[w.id];
                        else copy[w.id] = val;
                        return copy;
                      });
                    }}
                    className="px-2 py-1 rounded border border-slate-300 text-xs"
                  >
                    <option value="">-- Auto from Loom --</option>
                    <option value="PRESENT">PRESENT (1.0)</option>
                    <option value="HALF">HALF (0.5)</option>
                    <option value="ABSENT">ABSENT (0.0)</option>
                  </select>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void handleSaveAttendance()}
              className="px-3.5 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold"
            >
              Save Attendance Marks
            </button>
          </div>

          <div className="space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-amber-600" />
              Shed Working Calendar ({formatDateDMY(entryDate)})
            </h2>
            <label className="flex items-center gap-2 text-xs font-medium">
              <input
                type="checkbox"
                checked={isWorkingDay}
                onChange={(e) => setIsWorkingDay(e.target.checked)}
              />
              Shed Operating Normally (Uncheck for Weekly Off / Festival Shutdown)
            </label>
            <input
              value={calNote}
              onChange={(e) => setCalNote(e.target.value)}
              placeholder="Holiday / Maintenance note (optional)"
              className="w-full px-3 py-2 rounded border border-slate-300 text-xs"
            />
            <button
              type="button"
              onClick={() => void handleSaveCalendar()}
              className="px-3.5 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold"
            >
              Update Calendar Day
            </button>
          </div>
        </div>
      )}

      {/* Loom Shift Cards / Grid */}
      <form noValidate onSubmit={handleSaveGrid} className="space-y-3">
        <div className="grid md:grid-cols-2 gap-3">
          {rows.map((r, idx) => {
            const startMissing =
              r.entryMode === "COUNTER" &&
              ((r.startMeter === "" && r.endMeter !== "") || (attemptedSave && !hasValidMetresRow && idx === 0 && r.startMeter === ""));
            const endBad =
              r.entryMode === "COUNTER" &&
              ((r.startMeter !== "" && r.endMeter === "") ||
                (r.startMeter !== "" && r.endMeter !== "" && parseFloat(r.endMeter) < parseFloat(r.startMeter)) ||
                (attemptedSave && !hasValidMetresRow && idx === 0 && r.endMeter === ""));
            const directBad =
              r.entryMode === "DIRECT" &&
              ((r.netMetres !== "" && parseFloat(r.netMetres) < 0) || (attemptedSave && !hasValidMetresRow && idx === 0 && r.netMetres === ""));
            const defectBad = isRowDefectBad(r);
            const stopped = isRowStopped(r);
            const hasSwap = rows.some((x) => x.loomId === r.loomId && x.isSwapExtra);
            return (
            <div
              key={r.rowKey}
              className={`p-3.5 rounded-xl border space-y-2.5 ${
                r.isSwapExtra
                  ? "bg-amber-50/40 border-amber-300"
                  : stopped
                  ? "bg-rose-50/30 border-rose-200"
                  : "bg-white border-slate-200"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-bold text-sm text-slate-900">{r.loomNumber}</span>
                  <span className="text-[11px] text-slate-500">Shuttle · {r.ratedRpm} RPM</span>
                  {r.existingId && (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                      Saved
                    </span>
                  )}
                  {r.isSwapExtra && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-bold">
                      2nd Beam (Mid-Shift)
                    </span>
                  )}
                  {r.activeSortName && !r.isSwapExtra && (
                    <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-800 text-[10px] font-semibold">
                      {r.activeSortName} ({r.remainingBeamM ?? "?"}m left)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {/* Clear touchable Metres / Counter pill switch */}
                  <div
                    className="inline-flex rounded-md border border-slate-300 bg-slate-100 p-0.5 text-[11px] font-semibold"
                    title="Metres = type cloth metres directly | Counter = enter Start & End meter readings"
                  >
                    <button
                      type="button"
                      onClick={() => updateRow(r.rowKey, { entryMode: "DIRECT" })}
                      className={`px-2 py-0.5 rounded cursor-pointer transition ${
                        r.entryMode === "DIRECT"
                          ? "bg-slate-900 text-white shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Metres
                    </button>
                    <button
                      type="button"
                      onClick={() => updateRow(r.rowKey, { entryMode: "COUNTER" })}
                      className={`px-2 py-0.5 rounded cursor-pointer transition ${
                        r.entryMode === "COUNTER"
                          ? "bg-slate-900 text-white shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Counter
                    </button>
                  </div>

                  {!r.isSwapExtra && !hasSwap && (
                    <button
                      type="button"
                      onClick={() => addBeamSwapRow(r)}
                      className="text-[11px] font-semibold text-amber-700 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                      title="Split row ONLY if the warp beam was changed mid-shift on this loom"
                    >
                      <Plus className="w-3 h-3" /> Beam Swap
                    </button>
                  )}
                  {r.isSwapExtra && (
                    <button
                      type="button"
                      onClick={() => removeSwapRow(r.rowKey)}
                      className="text-[11px] font-semibold text-rose-600 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                    >
                      <X className="w-3 h-3" /> Remove
                    </button>
                  )}
                  {isOwner && r.existingId && (
                    <button
                      type="button"
                      onClick={() => setVoidTarget({ shiftId: r.existingId!, loomNumber: r.loomNumber })}
                      className="text-[11px] font-semibold text-rose-600 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                      title="Remove saved shift entry"
                    >
                      <Trash2 className="w-3 h-3" /> Void
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] font-medium text-slate-500 block mb-0.5">Weaver</label>
                  <select
                    value={r.weaverId}
                    onChange={(e) => updateRow(r.rowKey, { weaverId: Number(e.target.value) })}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
                  >
                    {weavers.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.full_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-slate-500 block mb-0.5">Warp Beam (optional)</label>
                  <select
                    value={r.beamId ?? ""}
                    onChange={(e) => updateRow(r.rowKey, { beamId: e.target.value ? Number(e.target.value) : null })}
                    className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
                  >
                    <option value="">-- No Beam Tag --</option>
                    {beams
                      .filter((b) => b.status !== "COMPLETED" || b.id === r.beamId)
                      .map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.beam_no} ({b.sort_name})
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              {r.entryMode === "COUNTER" ? (
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500 block">Start Meter</label>
                    <input
                      type="number"
                      step="0.01"
                      value={r.startMeter}
                      onChange={(e) => updateRow(r.rowKey, { startMeter: e.target.value })}
                      className={`w-full px-2 py-1.5 rounded border text-xs bg-white ${startMissing ? "field-invalid" : "border-slate-300"}`}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 block">End Meter</label>
                    <input
                      type="number"
                      step="0.01"
                      value={r.endMeter}
                      onChange={(e) => updateRow(r.rowKey, { endMeter: e.target.value })}
                      className={`w-full px-2 py-1.5 rounded border text-xs bg-white ${endBad ? "field-invalid" : "border-slate-300"}`}
                    />
                    {endBad && (
                      <p className="text-[10px] text-rose-600 font-medium mt-0.5">
                        {r.startMeter !== "" && r.endMeter !== "" && parseFloat(r.endMeter) < parseFloat(r.startMeter)
                          ? "Must be ≥ Start"
                          : "Required"}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 block">Net Metres</label>
                    <div className="w-full px-2 py-1.5 rounded border border-slate-200 bg-slate-50 text-xs font-bold text-slate-800 select-none">
                      {r.netMetres || "—"}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500 block">Metres Woven</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="e.g. 26.50"
                      value={r.netMetres}
                      onChange={(e) => updateRow(r.rowKey, { netMetres: e.target.value })}
                      className={`w-full px-2.5 py-1.5 rounded border text-sm font-semibold bg-white ${directBad ? "field-invalid" : "border-slate-300"}`}
                    />
                    {directBad && (
                      <p className="text-[10px] text-rose-600 font-medium mt-0.5">
                        {r.netMetres !== "" && parseFloat(r.netMetres) < 0 ? "Cannot be negative" : "Enter metres woven"}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 block">Confirmed Defect (m, optional)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={r.defectiveMetres}
                      onChange={(e) => updateRow(r.rowKey, { defectiveMetres: e.target.value })}
                      className={`w-full px-2.5 py-1.5 rounded border text-sm bg-white ${defectBad ? "field-invalid" : "border-slate-300"}`}
                    />
                  </div>
                </div>
              )}

              {/* Simple Running / Stopped Toggle (no stoppage minute boxes) */}
              <div className="flex items-center justify-between pt-1 border-t border-slate-100">
                <span className="text-[11px] font-medium text-slate-500">Loom Status in Shift:</span>
                <div className="inline-flex rounded-lg border border-slate-300 bg-slate-100 p-0.5 text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => toggleRowStatus(r, false)}
                    className={`px-3 py-1 rounded-md cursor-pointer transition ${
                      !stopped
                        ? "bg-emerald-600 text-white shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    ● Running
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleRowStatus(r, true)}
                    className={`px-3 py-1 rounded-md cursor-pointer transition ${
                      stopped
                        ? "bg-rose-600 text-white shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    ■ Stopped
                  </button>
                </div>
              </div>
            </div>
            );
          })}
        </div>

        <div className="mt-4 pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border">
          <div className="text-xs text-slate-600">
            Total Cloth in Grid (<span className="font-semibold text-slate-900">{formatDateDMY(entryDate)} · Shift {shiftNo}</span>):{" "}
            <span className="font-bold text-slate-900">{totalMetresEntered.toFixed(1)} m</span>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-sm shadow-sm inline-flex items-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            <Save className="w-4 h-4" />
            {saving ? "Saving Shift..." : `Save Shift ${shiftNo} (${formatDateDMY(entryDate)})`}
          </button>
        </div>
      </form>
    </div>
  );
}

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Plus,
  Save,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { apiRequest, formatDateDMY, generateUuid, localIsoDate, offsetLocalIsoDate } from "../api/client";
import { ConfirmVoidModal } from "../components/ConfirmVoidModal";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useLiveRefresh } from "../hooks/useLiveRefresh";
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
  const { user, tr } = useAuth();
  const toast = useToast();
  const isOwner = user?.role === "OWNER";

  const [activeTab, setActiveTab] = useState<"production" | "attendance">("production");
  const [entryDate, setEntryDate] = useState(localIsoDate());
  const [shiftNo, setShiftNo] = useState<number>(1);
  const [entryMode, setEntryMode] = useState<EntryMode>("DIRECT");
  const [prefill, setPrefill] = useState<ShiftPrefillResponse | null>(null);
  const [rows, setRows] = useState<EditableShiftRow[]>([]);
  const [expandedLoomIds, setExpandedLoomIds] = useState<Record<number, boolean>>({});
  const [weavers, setWeavers] = useState<Weaver[]>([]);
  const [beams, setBeams] = useState<Beam[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [attemptedSave, setAttemptedSave] = useState(false);
  const [lastSavedText, setLastSavedText] = useState<string | null>(null);
  const [voidTarget, setVoidTarget] = useState<{ shiftId: number; loomNumber: string } | null>(null);

  // Worker attendance & Holiday tab state
  const [attMap, setAttMap] = useState<Record<number, AttendanceStatus>>({});
  const [isWorkingDay, setIsWorkingDay] = useState(true);
  const [calNote, setCalNote] = useState("");
  const [initializedShiftAuto, setInitializedShiftAuto] = useState(false);

  const loadMastersAndPrefill = useCallback(
    async (targetDate: string, targetShift: number | null) => {
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
        if (!targetShift) {
          setShiftNo(pf.shift_no);
          setEntryMode(pf.default_entry_mode);
        }
        setWeavers(wv);
        setBeams(bm);
        setAlerts(al);

        const defaultWeaverId = wv[0]?.id ?? 0;
        const builtRows: EditableShiftRow[] = [];

        for (const lr of pf.looms) {
          if (lr.existing_entries.length > 0) {
            lr.existing_entries.forEach((ex, idx) => {
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
                isSwapExtra: idx > 0,
              });
            });
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
        toast.error(err instanceof Error ? err.message : tr("Failed to load shift grid", "ஷிப்ட் தகவலை ஏற்ற முடியவில்லை"));
      }
    },
    [toast, tr]
  );

  useEffect(() => {
    if (!initializedShiftAuto) {
      setInitializedShiftAuto(true);
      void loadMastersAndPrefill(entryDate, null);
    }
  }, [initializedShiftAuto, entryDate, loadMastersAndPrefill]);

  const refreshLive = useCallback(() => {
    void loadMastersAndPrefill(entryDate, shiftNo);
  }, [entryDate, shiftNo, loadMastersAndPrefill]);
  useLiveRefresh(refreshLive);

  const handleDateOrShiftChange = (nextDate: string, nextShift: number) => {
    setEntryDate(nextDate);
    setShiftNo(nextShift);
    setAttemptedSave(false);
    setLastSavedText(null);
    void loadMastersAndPrefill(nextDate, nextShift);
  };

  const applyGlobalMode = (nextMode: EntryMode) => {
    setEntryMode(nextMode);
    setRows((prev) => prev.map((r) => ({ ...r, entryMode: nextMode })));
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

  const addMidShiftSecondBeam = (src: EditableShiftRow) => {
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
    setRows((prev) => [...prev, newRow]);
    setExpandedLoomIds((prev) => ({ ...prev, [src.loomId]: true }));
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

  const validRows = rows.filter((r) => {
    if (isRowStopped(r)) return true;
    if (r.entryMode === "COUNTER") return r.startMeter !== "" && r.endMeter !== "";
    return r.netMetres !== "";
  });

  const handleSaveGrid = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttemptedSave(true);

    if (rows.some((r) => isRowCounterBad(r) || isRowDirectBad(r) || isRowDefectBad(r))) {
      toast.error(tr("Fix the highlighted invalid metre fields before saving.", "சிவப்பு நிற தவறான கட்டங்களை சரிசெய்து சேமிக்கவும்."));
      return;
    }
    if (validRows.length === 0) {
      toast.error(tr("Enter metres for at least one loom (or mark Stopped) before saving.", "குறைந்தது ஒரு தறியின் மீட்டரை உள்ளிட்டு சேமிக்கவும்."));
      return;
    }
    if (weavers.length === 0) {
      toast.error(tr("Add at least one Weaver in Shed Setup before logging shifts.", "அமைப்புகளில் ஒரு நெசவாளரைச் சேர்த்துவிட்டு ஷிப்ட் பதியவும்."));
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
      const msg = tr(
        `Saved ${saved.length} loom entr${saved.length === 1 ? "y" : "ies"} for ${formatDateDMY(entryDate)} (Shift ${shiftNo}).`,
        `${formatDateDMY(entryDate)} (ஷிப்ட் ${shiftNo}) — ${saved.length} தறி பதிவுகள் சேமிக்கப்பட்டன.`
      );
      setLastSavedText(msg);
      toast.success(msg);
      await loadMastersAndPrefill(entryDate, shiftNo);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tr("Failed to save shift entries", "ஷிப்ட் பதிவுகளை சேமிக்க முடியவில்லை"));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAttendance = async () => {
    const items = Object.entries(attMap).map(([wid, st]) => ({
      weaver_id: Number(wid),
      status: st,
    }));
    if (items.length === 0) {
      toast.info(tr("Select at least one worker status first.", "குறைந்தது ஒரு தொழிலாளர் நிலையைத் தேர்ந்தெடுக்கவும்."));
      return;
    }
    try {
      await apiRequest("/attendance/batch", {
        method: "POST",
        body: JSON.stringify({ attendance_date: entryDate, shift_no: shiftNo, items }),
      });
      toast.success(tr(`Attendance saved for Shift ${shiftNo} (${items.length} workers).`, `ஷிப்ட் ${shiftNo} வருகைப்பதிவு சேமிக்கப்பட்டது.`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tr("Failed to save attendance", "வருகைப்பதிவை சேமிக்க முடியவில்லை"));
    }
  };

  const handleSaveCalendar = async () => {
    try {
      await apiRequest(`/calendar/${entryDate}`, {
        method: "PUT",
        body: JSON.stringify({
          is_working_day: isWorkingDay,
          planned_shifts: isWorkingDay ? (prefill?.shifts_per_day ?? 2) : 0,
          note: calNote || null,
        }),
      });
      toast.success(tr(`Calendar updated for ${formatDateDMY(entryDate)}.`, `${formatDateDMY(entryDate)} நாள்காட்டி புதுப்பிக்கப்பட்டது.`));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tr("Failed to update calendar", "நாள்காட்டியைப் புதுப்பிக்க முடியவில்லை"));
    }
  };

  const dismissAlert = async (alertId: number) => {
    await apiRequest(`/alerts/${alertId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "DISMISSED" }),
    });
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    toast.info(tr("Alert dismissed.", "எச்சரிக்கை நீக்கப்பட்டது."));
  };

  const confirmVoidShift = async (reason: string) => {
    if (!voidTarget) return;
    try {
      await apiRequest(`/shifts/${voidTarget.shiftId}`, {
        method: "DELETE",
        body: JSON.stringify({ reason }),
      });
      const clearedNum = voidTarget.loomNumber;
      setVoidTarget(null);
      toast.success(tr(`Removed saved shift entry for ${clearedNum}.`, `${clearedNum} தறியின் ஷிப்ட் பதிவு நீக்கப்பட்டது.`));
      await loadMastersAndPrefill(entryDate, shiftNo);
    } catch (err) {
      setVoidTarget(null);
      toast.error(err instanceof Error ? err.message : tr("Failed to remove shift", "ஷிப்ட் பதிவை நீக்க முடியவில்லை"));
    }
  };

  const maxShifts = prefill?.shifts_per_day ?? 2;
  const totalMetresEntered = rows.reduce((acc, r) => acc + (parseFloat(r.netMetres || "0") || 0), 0);

  // Group primary loom row + optional mid-shift 2nd beam row under the SAME visual card
  const primaryRows = rows.filter((r) => !r.isSwapExtra);
  const swapByLoomId = new Map<number, EditableShiftRow>();
  for (const r of rows) {
    if (r.isSwapExtra) swapByLoomId.set(r.loomId, r);
  }

  return (
    <div className="space-y-4 pb-12">
      <ConfirmVoidModal
        open={Boolean(voidTarget)}
        title={tr(`Remove Saved Shift on ${voidTarget?.loomNumber ?? ""}?`, `${voidTarget?.loomNumber ?? ""} தறியின் ஷிப்ட் பதிவை நீக்கவா?`)}
        description={tr(
          "Removes this saved production entry while keeping an audit record.",
          "இந்த ஷிப்ட் உற்பத்தி பதிவு நீக்கப்படும்; மாற்றப் பதிவில் வரலாறு இருக்கும்."
        )}
        confirmLabel={tr("Remove Shift Entry", "பதிவை நீக்கு")}
        onCancel={() => setVoidTarget(null)}
        onConfirm={confirmVoidShift}
      />

      {/* Clean Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-amber-600" />
            {tr("Daily Production", "தினசரி உற்பத்தி")}
          </h1>
          <p className="text-xs text-slate-500">
            {formatDateDMY(entryDate)} · {tr(`Shift ${shiftNo}`, `ஷிப்ட் ${shiftNo}`)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="bg-slate-900 text-white px-3.5 py-2 rounded-xl text-xs font-semibold">
            {tr("Total", "மொத்தம்")}: <span className="text-amber-400 text-sm">{totalMetresEntered.toFixed(1)} m</span>
          </div>
        </div>
      </div>

      {/* Clean 2-Tab Bar (Production vs Attendance & Holiday) */}
      <div className="flex items-center gap-6 border-b border-slate-200 text-sm font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab("production")}
          className={`pb-2.5 border-b-2 transition cursor-pointer ${
            activeTab === "production"
              ? "border-amber-500 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          {tr("Loom Production", "தறி உற்பத்தி")}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("attendance")}
          className={`pb-2.5 border-b-2 transition cursor-pointer inline-flex items-center gap-1.5 ${
            activeTab === "attendance"
              ? "border-amber-500 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Users className="w-4 h-4" />
          {tr("Attendance & Holiday", "வருகை & விடுமுறை")}
        </button>
      </div>

      {/* Open Alerts (compact) */}
      {alerts.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-3.5 py-2.5 space-y-1">
          <div className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" /> {tr(`Open Alerts (${alerts.length})`, `எச்சரிக்கைகள் (${alerts.length})`)}
          </div>
          {alerts.slice(0, 3).map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-2 text-xs text-amber-900">
              <span className="truncate">{a.message}</span>
              <button
                type="button"
                onClick={() => void dismissAlert(a.id)}
                className="text-slate-600 hover:text-slate-900 underline shrink-0 cursor-pointer"
              >
                {tr("Dismiss", "நீக்கு")}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Single Clean Date, Shift & Entry Mode Bar */}
      <div className="bg-white p-3 rounded-2xl border border-slate-200 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleDateOrShiftChange(localIsoDate(), shiftNo)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${
              entryDate === localIsoDate()
                ? "bg-amber-500 text-slate-950 border-amber-500"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            {tr("Today", "இன்று")}
          </button>
          <button
            type="button"
            onClick={() => handleDateOrShiftChange(offsetLocalIsoDate(-1), shiftNo)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${
              entryDate === offsetLocalIsoDate(-1)
                ? "bg-amber-500 text-slate-950 border-amber-500"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            {tr("Yesterday", "நேற்று")}
          </button>
          <input
            type="date"
            value={entryDate}
            onChange={(e) => handleDateOrShiftChange(e.target.value, shiftNo)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs font-medium"
          />
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold">
            {[
              { no: 1, label: tr("Shift 1", "ஷிப்ட் 1") },
              ...(maxShifts >= 2 ? [{ no: 2, label: tr("Shift 2", "ஷிப்ட் 2") }] : []),
              ...(maxShifts >= 3 ? [{ no: 3, label: tr("Shift 3", "ஷிப்ட் 3") }] : []),
            ].map((s) => (
              <button
                key={s.no}
                type="button"
                onClick={() => handleDateOrShiftChange(entryDate, s.no)}
                className={`px-3 py-1 rounded-md cursor-pointer transition ${
                  shiftNo === s.no ? "bg-slate-900 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === "production" && (
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => applyGlobalMode("DIRECT")}
              className={`px-3 py-1 rounded-md cursor-pointer transition ${
                entryMode === "DIRECT" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tr("Direct Metres", "நேரடி மீட்டர்")}
            </button>
            <button
              type="button"
              onClick={() => applyGlobalMode("COUNTER")}
              className={`px-3 py-1 rounded-md cursor-pointer transition ${
                entryMode === "COUNTER" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tr("Meter Counter", "மீட்டர் எண்")}
            </button>
          </div>
        )}
      </div>

      {/* Tab 2: Attendance & Holiday */}
      {activeTab === "attendance" ? (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5 text-slate-900">
              <Users className="w-4 h-4 text-amber-600" />
              {tr(`Shift ${shiftNo} Worker Attendance`, `ஷிப்ட் ${shiftNo} தொழிலாளர் வருகை`)}
            </h2>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {weavers.map((w) => (
                <div key={w.id} className="flex items-center justify-between gap-2 text-xs bg-slate-50 px-3 py-2 rounded-lg">
                  <span>
                    <b className="text-slate-900">{w.full_name}</b> <span className="text-slate-500">({w.role_type})</span>
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
                    className="px-2.5 py-1 rounded-lg border border-slate-300 text-xs bg-white"
                  >
                    <option value="">{tr("Auto from Loom", "தறியிலிருந்து தானாக")}</option>
                    <option value="PRESENT">{tr("Present (1.0)", "வந்தவர் (1.0)")}</option>
                    <option value="HALF">{tr("Half Shift (0.5)", "அரை (0.5)")}</option>
                    <option value="ABSENT">{tr("Absent (0.0)", "விடுப்பு (0.0)")}</option>
                  </select>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void handleSaveAttendance()}
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold cursor-pointer"
            >
              {tr("Save Attendance", "வருகை சேமி")}
            </button>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-3">
            <h2 className="text-sm font-bold flex items-center gap-1.5 text-slate-900">
              <Calendar className="w-4 h-4 text-amber-600" />
              {tr("Working Day / Holiday", "வேலை நாள் / விடுமுறை")} ({formatDateDMY(entryDate)})
            </h2>
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={isWorkingDay}
                onChange={(e) => setIsWorkingDay(e.target.checked)}
              />
              {tr("Shed Operating Normally (uncheck for Holiday / Shutdown)", "ஆலை இயங்கும் (விடுமுறைக்கு டிக் நீக்கவும்)")}
            </label>
            <input
              value={calNote}
              onChange={(e) => setCalNote(e.target.value)}
              placeholder={tr("Holiday / Maintenance note (optional)", "விடுமுறை குறிப்பு (விருப்பம்)")}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
            />
            <button
              type="button"
              onClick={() => void handleSaveCalendar()}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold cursor-pointer"
            >
              {tr("Update Calendar Day", "நாள்காட்டி புதுப்பி")}
            </button>
          </div>
        </div>
      ) : (
        /* Tab 1: Clean Loom Production Cards */
        <form noValidate onSubmit={handleSaveGrid} className="space-y-4">
          <div className="grid md:grid-cols-2 gap-3.5">
            {primaryRows.map((r, idx) => {
              const swapRow = swapByLoomId.get(r.loomId);
              const isExpanded = Boolean(expandedLoomIds[r.loomId] || swapRow || parseFloat(r.defectiveMetres || "0") > 0);
              const stopped = isRowStopped(r);
              const startMissing =
                r.entryMode === "COUNTER" &&
                ((r.startMeter === "" && r.endMeter !== "") || (attemptedSave && validRows.length === 0 && idx === 0 && r.startMeter === ""));
              const endBad =
                r.entryMode === "COUNTER" &&
                ((r.startMeter !== "" && r.endMeter === "") ||
                  (r.startMeter !== "" && r.endMeter !== "" && parseFloat(r.endMeter) < parseFloat(r.startMeter)) ||
                  (attemptedSave && validRows.length === 0 && idx === 0 && r.endMeter === ""));
              const directBad =
                r.entryMode === "DIRECT" &&
                ((r.netMetres !== "" && parseFloat(r.netMetres) < 0) || (attemptedSave && validRows.length === 0 && idx === 0 && r.netMetres === ""));

              return (
                <div
                  key={r.rowKey}
                  className={`p-4 rounded-2xl border space-y-3 transition ${
                    stopped ? "bg-rose-50/35 border-rose-200" : "bg-white border-slate-200 shadow-2xs"
                  }`}
                >
                  {/* Row 1: Loom Name + Active Beam + Running/Stopped */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                      <span className="font-bold text-base text-slate-900">{r.loomNumber}</span>
                      {r.existingId && (
                        <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                          <CheckCircle2 className="w-3 h-3" /> {tr("Saved", "சேமிக்கப்பட்டது")}
                        </span>
                      )}
                      {r.activeSortName && (
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-medium truncate max-w-[160px]">
                          {r.activeSortName}
                        </span>
                      )}
                    </div>

                    <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-[11px] font-semibold shrink-0">
                      <button
                        type="button"
                        onClick={() => toggleRowStatus(r, false)}
                        className={`px-2.5 py-1 rounded-md cursor-pointer transition ${
                          !stopped ? "bg-emerald-600 text-white shadow-2xs" : "text-slate-600"
                        }`}
                      >
                        {tr("Running", "இயக்கம்")}
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleRowStatus(r, true)}
                        className={`px-2.5 py-1 rounded-md cursor-pointer transition ${
                          stopped ? "bg-rose-600 text-white shadow-2xs" : "text-slate-600"
                        }`}
                      >
                        {tr("Stopped", "நிறுத்தம்")}
                      </button>
                    </div>
                  </div>

                  {/* Row 2: Weaver + Metres (or Counter Start/End) */}
                  {r.entryMode === "COUNTER" ? (
                    <div className="space-y-2">
                      <div>
                        <label className="text-[11px] font-medium text-slate-500 block mb-1">{tr("Weaver", "நெசவாளர்")}</label>
                        <select
                          value={r.weaverId}
                          onChange={(e) => updateRow(r.rowKey, { weaverId: Number(e.target.value) })}
                          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white"
                        >
                          {weavers.map((w) => (
                            <option key={w.id} value={w.id}>
                              {w.full_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="text-[11px] text-slate-500 block mb-0.5">{tr("Start", "தொடக்கம்")}</label>
                          <input
                            type="number"
                            step="0.01"
                            value={r.startMeter}
                            onChange={(e) => updateRow(r.rowKey, { startMeter: e.target.value })}
                            className={`w-full px-2.5 py-2 rounded-lg border text-sm bg-white ${startMissing ? "field-invalid" : "border-slate-300"}`}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-500 block mb-0.5">{tr("End", "முடிவு")}</label>
                          <input
                            type="number"
                            step="0.01"
                            value={r.endMeter}
                            onChange={(e) => updateRow(r.rowKey, { endMeter: e.target.value })}
                            className={`w-full px-2.5 py-2 rounded-lg border text-sm bg-white ${endBad ? "field-invalid" : "border-slate-300"}`}
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-500 block mb-0.5">{tr("Net (m)", "மீட்டர்")}</label>
                          <div className="w-full px-2.5 py-2 rounded-lg border border-slate-200 bg-slate-50 text-sm font-bold text-slate-900">
                            {r.netMetres || "—"}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="text-[11px] font-medium text-slate-500 block mb-1">{tr("Weaver", "நெசவாளர்")}</label>
                        <select
                          value={r.weaverId}
                          onChange={(e) => updateRow(r.rowKey, { weaverId: Number(e.target.value) })}
                          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white h-[38px]"
                        >
                          {weavers.map((w) => (
                            <option key={w.id} value={w.id}>
                              {w.full_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] font-medium text-slate-500 block mb-1">{tr("Metres Woven", "நெய்த மீட்டர்")}</label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="e.g. 26.5"
                          value={r.netMetres}
                          onChange={(e) => updateRow(r.rowKey, { netMetres: e.target.value })}
                          className={`w-full px-3 py-2 rounded-lg border text-sm font-bold bg-white h-[38px] ${
                            directBad ? "field-invalid" : "border-slate-300"
                          }`}
                        />
                      </div>
                    </div>
                  )}

                  {/* Row 3: Subtle expandable extras (Beam / Defect / Mid-shift split / Void) */}
                  <div className="pt-1 border-t border-slate-100">
                    <div className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => setExpandedLoomIds((prev) => ({ ...prev, [r.loomId]: !isExpanded }))}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-900 cursor-pointer"
                      >
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        {tr("Beam, defect & split options", "பீம், சேதம் & கூடுதல்")}
                      </button>
                      {isOwner && r.existingId && (
                        <button
                          type="button"
                          onClick={() => setVoidTarget({ shiftId: r.existingId!, loomNumber: r.loomNumber })}
                          className="text-[11px] font-semibold text-rose-600 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                        >
                          <Trash2 className="w-3 h-3" /> {tr("Void", "நீக்கு")}
                        </button>
                      )}
                    </div>

                    {isExpanded && (
                      <div className="mt-2.5 space-y-2.5 pt-2 border-t border-slate-100">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] font-medium text-slate-500 block mb-0.5">{tr("Warp Beam", "பீம்")}</label>
                            <select
                              value={r.beamId ?? ""}
                              onChange={(e) => updateRow(r.rowKey, { beamId: e.target.value ? Number(e.target.value) : null })}
                              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
                            >
                              <option value="">{tr("-- No Beam --", "-- பீம் இல்லை --")}</option>
                              {beams
                                .filter((b) => b.status !== "COMPLETED" || b.id === r.beamId)
                                .map((b) => (
                                  <option key={b.id} value={b.id}>
                                    {b.beam_no} ({b.sort_name})
                                  </option>
                                ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] font-medium text-slate-500 block mb-0.5">{tr("Defect Metres", "சேத மீட்டர்")}</label>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={r.defectiveMetres}
                              onChange={(e) => updateRow(r.rowKey, { defectiveMetres: e.target.value })}
                              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
                            />
                          </div>
                        </div>

                        {/* Optional Mid-Shift 2nd Beam nested cleanly inside the SAME loom card */}
                        {!swapRow ? (
                          <div className="flex items-center justify-between gap-2 bg-slate-50 px-2.5 py-2 rounded-lg">
                            <span className="text-[11px] text-slate-500">
                              {tr("Beam finished mid-shift?", "ஷிப்ட் இடையில் புதிய பீம் ஏற்றியதா?")}
                            </span>
                            <button
                              type="button"
                              onClick={() => addMidShiftSecondBeam(r)}
                              className="text-[11px] font-semibold text-amber-700 hover:underline inline-flex items-center gap-0.5 shrink-0 cursor-pointer"
                            >
                              <Plus className="w-3 h-3" /> {tr("Add 2nd Beam", "2வது பீம் சேர்")}
                            </button>
                          </div>
                        ) : (
                          <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-2.5 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-amber-900">
                                {tr(`Part 2 — New Beam on ${r.loomNumber}`, `பகுதி 2 — ${r.loomNumber} புதிய பீம்`)}
                              </span>
                              <button
                                type="button"
                                onClick={() => removeSwapRow(swapRow.rowKey)}
                                className="text-[11px] font-semibold text-rose-600 hover:underline inline-flex items-center gap-0.5 cursor-pointer"
                              >
                                <X className="w-3 h-3" /> {tr("Remove", "நீக்கு")}
                              </button>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              <select
                                value={swapRow.beamId ?? ""}
                                onChange={(e) => updateRow(swapRow.rowKey, { beamId: e.target.value ? Number(e.target.value) : null })}
                                className="px-2 py-1.5 rounded-lg border border-amber-300 text-xs bg-white"
                              >
                                <option value="">{tr("Pick new beam...", "புதிய பீம் தேர்வு...")}</option>
                                {beams
                                  .filter((b) => b.status !== "COMPLETED" || b.id === swapRow.beamId)
                                  .map((b) => (
                                    <option key={b.id} value={b.id}>
                                      {b.beam_no} ({b.sort_name})
                                    </option>
                                  ))}
                              </select>
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                placeholder={tr("Part 2 metres", "பகுதி 2 மீட்டர்")}
                                value={swapRow.netMetres}
                                onChange={(e) => updateRow(swapRow.rowKey, { netMetres: e.target.value })}
                                className="px-2.5 py-1.5 rounded-lg border border-amber-300 text-xs font-semibold bg-white"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Clear Sticky-Style Save Bar with Instant Inline Status */}
          <div className="sticky bottom-16 md:bottom-3 z-10 bg-white/95 backdrop-blur border border-slate-200 shadow-lg p-3.5 rounded-2xl flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-0.5">
              <div className="text-xs text-slate-600">
                <b className="text-slate-900">{validRows.length}</b> / {rows.length} {tr("looms ready", "தறிகள் தயார்")} ·{" "}
                <b className="text-slate-900">{totalMetresEntered.toFixed(1)} m</b>
              </div>
              {lastSavedText && (
                <div className="text-[11px] font-semibold text-emerald-700 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {lastSavedText}
                </div>
              )}
            </div>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 active:scale-[0.98] text-slate-950 font-bold text-sm shadow-sm inline-flex items-center gap-2 disabled:opacity-50 cursor-pointer transition"
            >
              <Save className="w-4 h-4" />
              {saving
                ? tr("Saving...", "சேமிக்கிறது...")
                : tr(`Save Shift ${shiftNo}`, `ஷிப்ட் ${shiftNo} சேமி`)}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

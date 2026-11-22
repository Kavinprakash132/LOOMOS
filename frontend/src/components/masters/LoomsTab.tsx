import React, { useEffect, useState } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { apiRequest } from "../../api/client";
import { ConfirmVoidModal } from "../ConfirmVoidModal";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { Loom, LoomStatus, LoomType } from "../../types/api";

const LOOM_TYPES: { value: LoomType; label: string }[] = [
  { value: "SHUTTLE", label: "Shuttle" },
  { value: "RAPIER", label: "Rapier" },
  { value: "AIRJET", label: "Airjet" },
  { value: "WATERJET", label: "Waterjet" },
  { value: "PROJECTILE", label: "Projectile" },
];

export function LoomsTab({
  looms,
  onRefresh,
  onError,
}: {
  looms: Loom[];
  onRefresh: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const { tr } = useAuth();
  const toast = useToast();

  // Add panel (collapsed cleanly until user clicks "+ Add Looms")
  const [showAdd, setShowAdd] = useState(false);
  const [addMode, setAddMode] = useState<"single" | "bulk">("single");
  const [submitting, setSubmitting] = useState(false);

  // Shared specs
  const [loomType, setLoomType] = useState<LoomType>("SHUTTLE");
  const [rpm, setRpm] = useState("160");
  const [reedIn, setReedIn] = useState("56");
  const [clothIn, setClothIn] = useState("52");
  const [pick, setPick] = useState("60");

  // Single vs Bulk identifiers
  const [loomNumber, setLoomNumber] = useState("");
  const [bulkCount, setBulkCount] = useState("5");
  const [bulkPrefix, setBulkPrefix] = useState("S-");
  const [bulkStart, setBulkStart] = useState(String(looms.length + 1));

  // Inline row editor
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editRpm, setEditRpm] = useState("");
  const [editReed, setEditReed] = useState("");
  const [editCloth, setEditCloth] = useState("");
  const [editPick, setEditPick] = useState("");

  const [showArchived, setShowArchived] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Loom | null>(null);

  useEffect(() => {
    const activeCount = looms.filter((l) => l.is_active).length;
    setBulkStart(String(activeCount + 1));
  }, [looms]);

  const parseOptionalNumber = (raw: string): number | null => {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    const n = Number(trimmed);
    return Number.isFinite(n) && n > 0 ? n : null;
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    const rpmVal = parseInt(rpm, 10);
    const reedVal = parseInt(reedIn, 10);
    const clothVal = parseOptionalNumber(clothIn);
    const pickVal = parseOptionalNumber(pick);
    if (!Number.isFinite(rpmVal) || rpmVal < 40 || rpmVal > 2500) {
      toast.error(tr("Speed (RPM) must be between 40 and 2500.", "வேகம் (RPM) 40 முதல் 2500-க்குள் இருக்க வேண்டும்."));
      return;
    }
    if (!Number.isFinite(reedVal) || reedVal < 20 || reedVal > 220) {
      toast.error(tr("Reed space must be between 20 and 220 inches.", "ரீட் அளவு 20 முதல் 220 அங்குலத்திற்குள் இருக்க வேண்டும்."));
      return;
    }

    setSubmitting(true);
    try {
      if (addMode === "single") {
        if (!loomNumber.trim()) {
          toast.error(tr("Enter a loom number (e.g. S-06).", "தறி எண்ணை உள்ளிடவும் (எ.கா. S-06)."));
          return;
        }
        await apiRequest("/looms", {
          method: "POST",
          body: JSON.stringify({
            loom_number: loomNumber.trim(),
            loom_type: loomType,
            rated_rpm: rpmVal,
            reed_space_in: reedVal,
            cloth_width_in: clothVal,
            default_pick: pickVal ? Math.round(pickVal) : null,
          }),
        });
        toast.success(tr(`Loom ${loomNumber.trim()} added.`, `தறி ${loomNumber.trim()} சேர்க்கப்பட்டது.`));
        setLoomNumber("");
      } else {
        const cnt = Math.max(1, parseInt(bulkCount, 10) || 1);
        const startN = Math.max(1, parseInt(bulkStart, 10) || 1);
        await apiRequest("/looms/bulk", {
          method: "POST",
          body: JSON.stringify({
            count: cnt,
            prefix: bulkPrefix.trim() || "S-",
            start_number: startN,
            loom_type: loomType,
            rated_rpm: rpmVal,
            reed_space_in: reedVal,
            cloth_width_in: clothVal,
            default_pick: pickVal ? Math.round(pickVal) : null,
          }),
        });
        toast.success(tr(`Added ${cnt} looms cleanly.`, `${cnt} தறிகள் சேர்க்கப்பட்டன.`));
      }
      setShowAdd(false);
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("Failed to add loom", "தறியைச் சேர்க்க முடியவில்லை");
      onError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (l: Loom) => {
    setEditingId(l.id);
    setEditRpm(String(l.rated_rpm));
    setEditReed(String(l.reed_space_in));
    setEditCloth(l.cloth_width_in != null ? String(l.cloth_width_in) : "");
    setEditPick(l.default_pick != null ? String(l.default_pick) : "");
  };

  const saveEdit = async (l: Loom) => {
    const rpmVal = parseInt(editRpm, 10);
    const reedVal = parseInt(editReed, 10);
    if (!Number.isFinite(rpmVal) || rpmVal < 40 || rpmVal > 2500) {
      toast.error(tr("RPM must be between 40 and 2500.", "RPM 40 முதல் 2500-க்குள் இருக்க வேண்டும்."));
      return;
    }
    if (!Number.isFinite(reedVal) || reedVal < 20 || reedVal > 220) {
      toast.error(tr("Reed must be between 20 and 220 in.", "ரீட் 20 முதல் 220 அங்குலத்திற்குள் இருக்க வேண்டும்."));
      return;
    }
    try {
      await apiRequest(`/looms/${l.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          rated_rpm: rpmVal,
          reed_space_in: reedVal,
          cloth_width_in: parseOptionalNumber(editCloth),
          default_pick: parseOptionalNumber(editPick) ? Math.round(parseOptionalNumber(editPick)!) : null,
        }),
      });
      setEditingId(null);
      toast.success(tr(`Updated ${l.loom_number}.`, `${l.loom_number} புதுப்பிக்கப்பட்டது.`));
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Update failed";
      onError(msg);
      toast.error(msg);
    }
  };

  const updateStatusOrActive = async (id: number, loomNum: string, patch: Partial<Pick<Loom, "status" | "is_active">>) => {
    try {
      await apiRequest(`/looms/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
      toast.success(tr(`Updated ${loomNum}.`, `${loomNum} நிலை புதுப்பிக்கப்பட்டது.`));
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Update failed";
      onError(msg);
      toast.error(msg);
    }
  };

  const deleteLoom = async (loom: Loom) => {
    try {
      const res = await apiRequest<{ status: string; message: string }>(`/looms/${loom.id}`, { method: "DELETE" });
      toast.success(res.message);
      await onRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete loom";
      onError(msg);
      toast.error(msg);
    }
  };

  const archivedCount = looms.filter((l) => !l.is_active).length;
  const activeCount = looms.filter((l) => l.is_active).length;
  const visibleLooms = showArchived ? looms : looms.filter((l) => l.is_active);
  const cntNum = Math.max(1, parseInt(bulkCount, 10) || 1);
  const startNum = Math.max(1, parseInt(bulkStart, 10) || 1);

  return (
    <div className="space-y-4">
      <ConfirmVoidModal
        open={Boolean(deleteTarget)}
        title={tr(`Delete Loom ${deleteTarget?.loom_number ?? ""}?`, `தறி ${deleteTarget?.loom_number ?? ""}-ஐ நீக்கவா?`)}
        description={tr(
          "Unused looms are deleted permanently. Looms with past shift or beam history are safely archived.",
          "பயன்படுத்தாத தறிகள் நிரந்தரமாக நீக்கப்படும். பழைய பதிவு உள்ள தறிகள் பாதுகாப்பாக நிறுத்தி வைக்கப்படும்."
        )}
        confirmLabel={tr("Confirm Delete / Archive", "நீக்கு / நிறுத்து")}
        requireReason={false}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          const target = deleteTarget;
          setDeleteTarget(null);
          await deleteLoom(target);
        }}
      />

      {/* Clean Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-slate-700">
          {tr(`${activeCount} Active Looms`, `${activeCount} இயங்கும் தறிகள்`)}
          {archivedCount > 0 && (
            <label className="ml-4 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 cursor-pointer">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              {tr(`Show archived (${archivedCount})`, `நிறுத்தியவை (${archivedCount})`)}
            </label>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowAdd((v) => !v)}
          className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer shadow-xs"
        >
          {showAdd ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4 text-amber-400" />}
          {showAdd ? tr("Close", "மூடு") : tr("Add Looms", "தறி சேர்")}
        </button>
      </div>

      {/* Single Clean Add Panel */}
      {showAdd && (
        <form onSubmit={handleAddSubmit} className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-slate-900">{tr("New Loom Details", "புதிய தறி விவரங்கள்")}</h3>
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setAddMode("single")}
                className={`px-3 py-1 rounded-md cursor-pointer transition ${
                  addMode === "single" ? "bg-slate-900 text-white" : "text-slate-600"
                }`}
              >
                {tr("Single Loom", "ஒரு தறி")}
              </button>
              <button
                type="button"
                onClick={() => setAddMode("bulk")}
                className={`px-3 py-1 rounded-md cursor-pointer transition ${
                  addMode === "bulk" ? "bg-slate-900 text-white" : "text-slate-600"
                }`}
              >
                {tr("Multiple Looms", "பல தறிகள்")}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            {addMode === "single" ? (
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  {tr("Loom #", "தறி எண்")} *
                </label>
                <input
                  required
                  placeholder="S-06"
                  value={loomNumber}
                  onChange={(e) => setLoomNumber(e.target.value)}
                  className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Count", "எண்ணிக்கை")}</label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={200}
                    value={bulkCount}
                    onChange={(e) => setBulkCount(e.target.value)}
                    className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Prefix", "குறியீடு")}</label>
                  <input
                    required
                    value={bulkPrefix}
                    onChange={(e) => setBulkPrefix(e.target.value)}
                    className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Start #", "தொடக்கம்")}</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={bulkStart}
                    onChange={(e) => setBulkStart(e.target.value)}
                    className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
              </>
            )}

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Type", "வகை")}</label>
              <select
                value={loomType}
                onChange={(e) => setLoomType(e.target.value as LoomType)}
                className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              >
                {LOOM_TYPES.map((lt) => (
                  <option key={lt.value} value={lt.value}>
                    {lt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Speed (RPM)", "வேகம் (RPM)")} *</label>
              <input
                type="number"
                required
                min={40}
                max={2500}
                value={rpm}
                onChange={(e) => setRpm(e.target.value)}
                className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Reed (in)", "ரீட் (அங்.)")} *</label>
              <input
                type="number"
                required
                min={20}
                max={220}
                value={reedIn}
                onChange={(e) => setReedIn(e.target.value)}
                className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Cloth Width (in)", "துணி அகலம் (அங்.)")}</label>
              <input
                type="number"
                step="0.5"
                min={10}
                max={220}
                placeholder="52"
                value={clothIn}
                onChange={(e) => setClothIn(e.target.value)}
                className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Pick (PPI)", "பிக் (Pick)")}</label>
              <input
                type="number"
                min={1}
                max={500}
                placeholder="60"
                value={pick}
                onChange={(e) => setPick(e.target.value)}
                className="w-full px-2.5 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 rounded-xl border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 cursor-pointer"
            >
              {tr("Cancel", "ரத்து")}
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold cursor-pointer disabled:opacity-50"
            >
              {addMode === "single"
                ? tr("Save Loom", "தறி சேமி")
                : `${tr("Generate", "உருவாக்கு")} ${cntNum} (${bulkPrefix}${String(startNum).padStart(2, "0")}..${bulkPrefix}${String(
                    startNum + cntNum - 1
                  ).padStart(2, "0")})`}
            </button>
          </div>
        </form>
      )}

      {/* Clean Loom Registry Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500 font-bold">
            <tr>
              <th className="px-4 py-3 text-left">{tr("Loom", "தறி")}</th>
              <th className="px-4 py-3 text-left">{tr("Reed · Cloth · Pick", "ரீட் · அகலம் · பிக்")}</th>
              <th className="px-4 py-3 text-left">{tr("RPM", "வேகம்")}</th>
              <th className="px-4 py-3 text-left">{tr("Status", "நிலை")}</th>
              <th className="px-4 py-3 text-right">{tr("Actions", "செயல்")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visibleLooms.map((l) => {
              const isEditing = editingId === l.id;
              return (
                <tr key={l.id} className={l.is_active ? "hover:bg-slate-50/70" : "opacity-55 bg-slate-50"}>
                  <td className="px-4 py-3">
                    <div className="font-bold text-slate-900">{l.loom_number}</div>
                    <div className="text-[11px] text-slate-500">{l.loom_type}</div>
                  </td>

                  <td className="px-4 py-3 text-xs">
                    {isEditing ? (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <input
                          type="number"
                          value={editReed}
                          onChange={(e) => setEditReed(e.target.value)}
                          placeholder="Reed"
                          title="Reed (in)"
                          className="w-16 px-2 py-1 rounded border border-slate-300 text-xs"
                        />
                        <input
                          type="number"
                          step="0.5"
                          value={editCloth}
                          onChange={(e) => setEditCloth(e.target.value)}
                          placeholder="Cloth"
                          title="Cloth Width (in)"
                          className="w-16 px-2 py-1 rounded border border-slate-300 text-xs"
                        />
                        <input
                          type="number"
                          value={editPick}
                          onChange={(e) => setEditPick(e.target.value)}
                          placeholder="Pick"
                          title="Pick (PPI)"
                          className="w-16 px-2 py-1 rounded border border-slate-300 text-xs"
                        />
                      </div>
                    ) : (
                      <div className="flex flex-wrap items-center gap-1.5 text-slate-700 font-medium">
                        <span className="px-2 py-0.5 rounded bg-slate-100">{l.reed_space_in}&Prime; {tr("reed", "ரீட்")}</span>
                        {l.cloth_width_in != null && (
                          <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-900">
                            {Number(l.cloth_width_in)}&Prime; {tr("cloth", "அகலம்")}
                          </span>
                        )}
                        {l.default_pick != null && (
                          <span className="px-2 py-0.5 rounded bg-sky-50 text-sky-900">
                            {l.default_pick} {tr("pick", "பிக்")}
                          </span>
                        )}
                      </div>
                    )}
                  </td>

                  <td className="px-4 py-3 text-xs font-semibold text-slate-800">
                    {isEditing ? (
                      <input
                        type="number"
                        min={40}
                        max={2500}
                        value={editRpm}
                        onChange={(e) => setEditRpm(e.target.value)}
                        className="w-20 px-2 py-1 rounded border border-slate-300 text-xs"
                      />
                    ) : (
                      `${l.rated_rpm} RPM`
                    )}
                  </td>

                  <td className="px-4 py-3">
                    <select
                      value={l.status}
                      onChange={(e) => void updateStatusOrActive(l.id, l.loom_number, { status: e.target.value as LoomStatus })}
                      className="px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium bg-white"
                    >
                      <option value="OPERATIONAL">{tr("Operational", "இயக்கத்தில்")}</option>
                      <option value="UNDER_MAINTENANCE">{tr("Maintenance", "பழுதுபார்ப்பு")}</option>
                      <option value="IDLE">{tr("Idle", "நிறுத்தம்")}</option>
                    </select>
                  </td>

                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-2">
                      {isEditing ? (
                        <>
                          <button
                            type="button"
                            onClick={() => void saveEdit(l)}
                            className="p-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer"
                            title={tr("Save", "சேமி")}
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="p-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 cursor-pointer"
                            title={tr("Cancel", "ரத்து")}
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </>
                      ) : !l.is_active ? (
                        <button
                          type="button"
                          onClick={() => void updateStatusOrActive(l.id, l.loom_number, { is_active: true, status: "OPERATIONAL" })}
                          className="text-xs font-semibold text-amber-700 hover:underline cursor-pointer"
                        >
                          {tr("Restore", "மீட்டமை")}
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => startEdit(l)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 cursor-pointer"
                            title={tr("Edit specs", "விவரம் திருத்து")}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(l)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                            title={tr("Delete / archive", "நீக்கு")}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

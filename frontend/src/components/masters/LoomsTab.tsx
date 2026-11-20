import React, { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { apiRequest } from "../../api/client";
import { ConfirmVoidModal } from "../ConfirmVoidModal";
import { useAuth } from "../../context/AuthContext";
import { Loom, LoomStatus } from "../../types/api";

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
  const [loomNumber, setLoomNumber] = useState("");
  const [rpm, setRpm] = useState(160);
  const [bulkCount, setBulkCount] = useState(5);
  const [bulkPrefix, setBulkPrefix] = useState("S-");
  const [bulkStart, setBulkStart] = useState(looms.length + 1);
  const [bulkRpm, setBulkRpm] = useState(160);
  const [showArchived, setShowArchived] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [rpmDrafts, setRpmDrafts] = useState<Record<number, string>>({});
  const [savedLoomId, setSavedLoomId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Loom | null>(null);

  useEffect(() => {
    const next: Record<number, string> = {};
    for (const l of looms) next[l.id] = String(l.rated_rpm);
    setRpmDrafts(next);
    const activeCount = looms.filter((l) => l.is_active).length;
    setBulkStart(activeCount + 1);
  }, [looms]);

  const handleAddSingle = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    try {
      await apiRequest("/looms", {
        method: "POST",
        body: JSON.stringify({ loom_number: loomNumber, loom_type: "SHUTTLE", rated_rpm: rpm }),
      });
      setLoomNumber("");
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add loom");
    }
  };

  const handleBulkAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    try {
      await apiRequest("/looms/bulk", {
        method: "POST",
        body: JSON.stringify({
          count: bulkCount,
          prefix: bulkPrefix,
          start_number: bulkStart,
          loom_type: "SHUTTLE",
          rated_rpm: bulkRpm,
        }),
      });
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Bulk creation failed");
    }
  };

  const updateLoom = async (
    id: number,
    patch: Partial<Pick<Loom, "status" | "is_active" | "rated_rpm">>
  ) => {
    try {
      await apiRequest(`/looms/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
      setSavedLoomId(id);
      setTimeout(() => setSavedLoomId((cur) => (cur === id ? null : cur)), 2000);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const deleteLoom = async (loom: Loom) => {
    setNotice(null);
    try {
      const res = await apiRequest<{ status: string; message: string }>(`/looms/${loom.id}`, {
        method: "DELETE",
      });
      setNotice(res.message);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to delete loom");
    }
  };

  const saveLoomRpm = async (loom: Loom) => {
    const parsed = parseInt(rpmDrafts[loom.id] ?? "", 10);
    if (Number.isNaN(parsed) || parsed < 40 || parsed > 2500) {
      onError(`RPM for ${loom.loom_number} must be between 40 and 2500.`);
      return;
    }
    if (parsed !== loom.rated_rpm) {
      await updateLoom(loom.id, { rated_rpm: parsed });
    }
  };

  const archivedCount = looms.filter((l) => !l.is_active).length;
  const visibleLooms = showArchived ? looms : looms.filter((l) => l.is_active);

  return (
    <div className="space-y-4">
      <ConfirmVoidModal
        open={Boolean(deleteTarget)}
        title={tr(`Delete Loom ${deleteTarget?.loom_number ?? ""}?`, `தறி ${deleteTarget?.loom_number ?? ""}-ஐ நீக்கவா?`)}
        description={tr(
          "Unused looms are deleted permanently. Looms with past shift or beam history are safely archived (and can be restored via Show Archived Looms).",
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
      {notice && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
          {notice}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <form onSubmit={handleAddSingle} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">{tr("Add Single Shuttle Loom", "ஒரு விசைத்தறி சேர்")}</h3>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Loom Number", "தறி எண்")} <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. S-06"
                value={loomNumber}
                onChange={(e) => setLoomNumber(e.target.value)}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Rated Speed (RPM)", "வேகம் (RPM)")} <span className="text-rose-600">*</span>
              </label>
              <input
                type="number"
                required
                min={40}
                max={2500}
                value={rpm}
                onChange={(e) => setRpm(Number(e.target.value))}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
            {tr("Add Shuttle Loom", "தறி சேர்")}
          </button>
        </form>

        <form onSubmit={handleBulkAdd} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">{tr("Bulk Generate Shuttle Looms", "ஒரே நேரத்தில் பல தறிகள் சேர்")}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("How Many", "எத்தனை")}</label>
              <input
                type="number"
                required
                min={1}
                value={bulkCount}
                onChange={(e) => setBulkCount(Number(e.target.value))}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Prefix (e.g. S-)", "குறியீடு (எ.கா. S-)")}</label>
              <input
                required
                value={bulkPrefix}
                onChange={(e) => setBulkPrefix(e.target.value)}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Start #", "தொடக்க எண்")}</label>
              <input
                type="number"
                required
                min={1}
                value={bulkStart}
                onChange={(e) => setBulkStart(Number(e.target.value))}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Speed (RPM)", "வேகம் (RPM)")}</label>
              <input
                type="number"
                required
                min={40}
                max={2500}
                value={bulkRpm}
                onChange={(e) => setBulkRpm(Number(e.target.value))}
                className="w-full px-2.5 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-amber-500 text-slate-950 text-xs font-bold">
            {tr(`Generate ${bulkCount} Looms`, `${bulkCount} தறிகள் உருவாக்கு`)} ({bulkPrefix}
            {String(bulkStart).padStart(2, "0")}..{bulkPrefix}
            {String(bulkStart + Math.max(0, bulkCount - 1)).padStart(2, "0")})
          </button>
        </form>
      </div>

      {archivedCount > 0 && (
        <div className="flex justify-end">
          <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            {tr(`Show Archived Looms (${archivedCount})`, `நிறுத்திய தறிகளைக் காட்டு (${archivedCount})`)}
          </label>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100 text-xs text-slate-700 font-semibold">
            <tr>
              <th className="px-3 py-2.5 text-left">{tr("Loom #", "தறி எண்")}</th>
              <th className="px-3 py-2.5 text-left">{tr("Machine Type", "இயந்திர வகை")}</th>
              <th className="px-3 py-2.5 text-left">{tr("Speed (RPM)", "வேகம் (RPM)")}</th>
              <th className="px-3 py-2.5 text-left">{tr("Running Status", "நிலை")}</th>
              <th className="px-3 py-2.5 text-left">{tr("Actions", "செயல்")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visibleLooms.map((l) => {
              const draft = rpmDrafts[l.id] ?? String(l.rated_rpm);
              const parsedDraft = parseInt(draft, 10);
              const rpmInvalid = Number.isNaN(parsedDraft) || parsedDraft < 40 || parsedDraft > 2500;
              const rpmDirty = draft !== String(l.rated_rpm);
              return (
                <tr key={l.id} className={l.is_active ? "" : "opacity-55 bg-slate-50"}>
                  <td className="px-3 py-2 font-semibold">{l.loom_number}</td>
                  <td className="px-3 py-2 text-xs text-slate-600">{tr("Shuttle Loom", "விசைத்தறி")}</td>
                  <td className="px-3 py-2 text-xs">
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        min={40}
                        max={2500}
                        value={draft}
                        onChange={(e) =>
                          setRpmDrafts((prev) => ({ ...prev, [l.id]: e.target.value }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void saveLoomRpm(l);
                          }
                        }}
                        className={`w-20 px-2 py-1 rounded border text-xs bg-white ${
                          rpmInvalid ? "field-invalid" : "border-slate-300"
                        }`}
                      />
                      {rpmDirty && (
                        <button
                          type="button"
                          onClick={() => void saveLoomRpm(l)}
                          className="px-2 py-1 rounded bg-slate-900 text-white text-[11px] font-semibold hover:bg-slate-800 cursor-pointer"
                        >
                          {tr("Save", "சேமி")}
                        </button>
                      )}
                      {savedLoomId === l.id && !rpmDirty && (
                        <span className="text-[11px] font-semibold text-emerald-700">{tr("Saved", "சேமிக்கப்பட்டது")}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={l.status}
                      onChange={(e) => void updateLoom(l.id, { status: e.target.value as LoomStatus })}
                      className="px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                    >
                      <option value="OPERATIONAL">{tr("OPERATIONAL", "இயக்கத்தில்")}</option>
                      <option value="UNDER_MAINTENANCE">{tr("UNDER_MAINTENANCE", "பழுதுபார்ப்பு")}</option>
                      <option value="IDLE">{tr("IDLE", "நிறுத்தம்")}</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-3">
                      {!l.is_active ? (
                        <button
                          type="button"
                          onClick={() => void updateLoom(l.id, { is_active: true, status: "OPERATIONAL" })}
                          className="text-xs font-semibold text-amber-700 hover:underline cursor-pointer"
                        >
                          {tr("Restore", "மீட்டமை")}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(l)}
                          className="text-xs font-semibold text-rose-600 hover:underline inline-flex items-center gap-1 cursor-pointer"
                          title={tr("Delete unused loom or archive if it has past shifts", "தறியை நீக்கு அல்லது நிறுத்து")}
                        >
                          <Trash2 className="w-3.5 h-3.5" /> {tr("Delete", "நீக்கு")}
                        </button>
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

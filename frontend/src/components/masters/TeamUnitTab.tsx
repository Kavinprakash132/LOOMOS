import React, { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { apiRequest, formatHoursFromMins } from "../../api/client";
import { PasswordInput } from "../PasswordInput";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { UnitSettings, User } from "../../types/api";

export function TeamUnitTab({
  settings,
  users,
  onRefresh,
  onError,
}: {
  settings: UnitSettings | null;
  users: User[];
  onRefresh: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const { t, tr } = useAuth();
  const toast = useToast();
  const [showAddSup, setShowAddSup] = useState(false);
  const [unitName, setUnitName] = useState(settings?.unit_name ?? "");
  const [location, setLocation] = useState(settings?.location ?? "");
  const [sanctionedKw, setSanctionedKw] = useState(settings?.sanctioned_kw ?? "10.00");
  const [shiftsPerDay, setShiftsPerDay] = useState(settings?.shifts_per_day ?? 2);
  const [plannedShiftMins, setPlannedShiftMins] = useState(settings?.planned_shift_mins ?? 600);

  useEffect(() => {
    if (settings) {
      setUnitName(settings.unit_name);
      setLocation(settings.location);
      setSanctionedKw(settings.sanctioned_kw);
      setShiftsPerDay(settings.shifts_per_day);
      setPlannedShiftMins(settings.planned_shift_mins);
    }
  }, [settings]);

  const [supName, setSupName] = useState("");
  const [supUser, setSupUser] = useState("");
  const [supPass, setSupPass] = useState("");

  const saveUnit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/settings", {
        method: "PATCH",
        body: JSON.stringify({
          unit_name: unitName,
          location,
          sanctioned_kw: sanctionedKw,
          shifts_per_day: shiftsPerDay,
          planned_shift_mins: Number(plannedShiftMins),
        }),
      });
      toast.success(tr("Shed settings saved.", "ஆலை அமைப்புகள் சேமிக்கப்பட்டன."));
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save settings");
    }
  };

  const addSupervisor = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/auth/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: supName,
          username: supUser,
          password: supPass,
          role: "SUPERVISOR",
          preferred_lang: "en",
        }),
      });
      const addedSup = supName.trim();
      setSupName("");
      setSupUser("");
      setSupPass("");
      setShowAddSup(false);
      toast.success(tr(`Supervisor ${addedSup} added.`, `மேற்பார்வையாளர் ${addedSup} சேர்க்கப்பட்டார்.`));
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add supervisor");
    }
  };

  const toggleUser = async (u: User) => {
    try {
      await apiRequest(`/auth/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      toast.success(
        u.is_active
          ? tr(`${u.full_name} deactivated.`, `${u.full_name} நிறுத்தப்பட்டார்.`)
          : tr(`${u.full_name} activated.`, `${u.full_name} செயல்படுத்தப்பட்டார்.`)
      );
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to update user");
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={saveUnit} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
        <h3 className="text-sm font-bold">{tr("Shed Settings", "ஆலை அமைப்புகள்")}</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              {tr("Shed / Unit Name", "ஆலை / தறிக்கூட பெயர்")} <span className="text-rose-600">*</span>
            </label>
            <input
              required
              value={unitName}
              onChange={(e) => setUnitName(e.target.value)}
              placeholder="e.g. LOOMOS"
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              {tr("Town / Location", "ஊர் / பகுதி")}
            </label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Palladam, Tiruppur"
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              {tr("Sanctioned EB Power Load (kW)", "அனுமதி EB மின் சுமை (kW)")}
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={sanctionedKw}
              onChange={(e) => setSanctionedKw(e.target.value)}
              placeholder="e.g. 10.00"
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              {tr("Shifts Per Day", "ஒரு நாளைக்கு ஷிப்டுகள்")}
            </label>
            <select
              value={shiftsPerDay}
              onChange={(e) => setShiftsPerDay(Number(e.target.value))}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
            >
              <option value={1}>{tr("1 Shift / Day", "1 ஷிப்ட் / நாள்")}</option>
              <option value={2}>{tr("2 Shifts / Day (Day & Night)", "2 ஷிப்ட் / நாள் (பகல் & இரவு)")}</option>
              <option value={3}>{tr("3 Shifts / Day", "3 ஷிப்ட் / நாள்")}</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              {tr(
                `Shift Duration (${formatHoursFromMins(plannedShiftMins)} hrs · enter mins, e.g. 600 = 10.00 hrs)`,
                `ஷிப்ட் நேரம் (${formatHoursFromMins(plannedShiftMins)} மணி · நிமிடங்களில், எ.கா. 600 = 10 மணி)`
              )}
            </label>
            <input
              type="number"
              min={60}
              max={1440}
              value={plannedShiftMins}
              onChange={(e) => setPlannedShiftMins(Number(e.target.value))}
              placeholder="600"
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
          {tr("Save Shed Settings", "அமைப்புகளை சேமி")}
        </button>
      </form>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-slate-900">
            {tr(`Team Accounts (${users.length})`, `பயனர் கணக்குகள் (${users.length})`)}
          </h3>
          <button
            type="button"
            onClick={() => setShowAddSup((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
              showAddSup ? "bg-slate-200 text-slate-800" : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            {showAddSup ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {showAddSup ? tr("Close", "மூடு") : tr("Add Supervisor", "மேற்பார்வையாளர் சேர்")}
          </button>
        </div>

        {showAddSup && (
        <form onSubmit={addSupervisor} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
          <div className="text-xs font-semibold text-slate-700">
            {tr("New Supervisor (Shift & Photo Access Only)", "புதிய மேற்பார்வையாளர் (ஷிப்ட் & படம் மட்டும்)")}
          </div>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Supervisor Full Name", "மேற்பார்வையாளர் பெயர்")} <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. Siva M"
                value={supName}
                onChange={(e) => setSupName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Login Username", "பயனர் பெயர்")} <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. sup_siva"
                value={supUser}
                onChange={(e) => setSupUser(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Password (min 6 chars)", "கடவுச்சொல் (6+ எழுத்துகள்)")} <span className="text-rose-600">*</span>
              </label>
              <PasswordInput
                required
                minLength={6}
                autoComplete="new-password"
                placeholder={tr("6+ characters", "6+ எழுத்துகள்")}
                value={supPass}
                onChange={(e) => setSupPass(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold cursor-pointer">
            {tr("Create Supervisor", "மேற்பார்வையாளர் உருவாக்கு")}
          </button>
        </form>
        )}

        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {users.map((u) => (
            <div key={u.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
              <div>
                <span className="font-semibold">{u.full_name}</span>
                <span className="ml-2 text-xs font-mono text-slate-500">@{u.username}</span>
                <span className="ml-2 px-2 py-0.5 rounded bg-slate-100 text-[11px] font-semibold">{t(`role_${u.role}`)}</span>
              </div>
              <button
                type="button"
                onClick={() => void toggleUser(u)}
                className="text-xs font-semibold text-amber-700 hover:underline cursor-pointer"
              >
                {u.is_active ? tr("Active (Deactivate)", "செயலில் (நிறுத்து)") : tr("Inactive (Activate)", "நிறுத்தப்பட்டது (இயக்கு)")}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

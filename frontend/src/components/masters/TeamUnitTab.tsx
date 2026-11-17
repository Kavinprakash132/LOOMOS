import React, { useEffect, useState } from "react";
import { apiRequest, formatHoursFromMins } from "../../api/client";
import { PasswordInput } from "../PasswordInput";
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
      setSupName("");
      setSupUser("");
      setSupPass("");
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
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to update user");
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={saveUnit} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
        <h3 className="text-sm font-bold">Shed Settings</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Shed / Unit Name <span className="text-rose-600">*</span>
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
              Town / Location
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
              Sanctioned EB Power Load (kW)
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
              Shifts Per Day
            </label>
            <select
              value={shiftsPerDay}
              onChange={(e) => setShiftsPerDay(Number(e.target.value))}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
            >
              <option value={1}>1 Shift / Day</option>
              <option value={2}>2 Shifts / Day (Day &amp; Night)</option>
              <option value={3}>3 Shifts / Day</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Shift Duration ({formatHoursFromMins(plannedShiftMins)} hrs · enter mins, e.g. 600 = 10.00 hrs)
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
          Save Shed Settings
        </button>
      </form>

      <form onSubmit={addSupervisor} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
        <h3 className="text-sm font-bold">Create Supervisor Account (Shift &amp; Photo Access Only)</h3>
        <div className="grid sm:grid-cols-3 gap-2">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Supervisor Full Name <span className="text-rose-600">*</span>
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
              Login Username <span className="text-rose-600">*</span>
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
              Password (min 6 chars) <span className="text-rose-600">*</span>
            </label>
            <PasswordInput
              required
              minLength={6}
              autoComplete="new-password"
              placeholder="6+ characters"
              value={supPass}
              onChange={(e) => setSupPass(e.target.value)}
              className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="px-4 py-2 rounded-lg bg-amber-500 text-slate-950 text-xs font-bold">
          Add Supervisor
        </button>
      </form>

      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
        {users.map((u) => (
          <div key={u.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
            <div>
              <span className="font-semibold">{u.full_name}</span>
              <span className="ml-2 text-xs font-mono text-slate-500">@{u.username}</span>
              <span className="ml-2 px-2 py-0.5 rounded bg-slate-100 text-[11px] font-semibold">{u.role}</span>
            </div>
            <button
              type="button"
              onClick={() => void toggleUser(u)}
              className="text-xs font-semibold text-amber-700 hover:underline"
            >
              {u.is_active ? "Active (Deactivate)" : "Inactive (Activate)"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

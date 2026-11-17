import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Gauge, IndianRupee, Layers } from "lucide-react";
import { apiRequest, formatDateDMY, formatHoursFromMins, formatRupeesFromPaise, localIsoDate, offsetLocalIsoDate } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { FloorDashboard, OwnerDashboard } from "../types/api";

export function DashboardPage() {
  const { user } = useAuth();
  const isOwner = user?.role === "OWNER";

  const [rangeMode, setRangeMode] = useState<"weekly" | "monthly" | "custom">("weekly");
  const [fromDate, setFromDate] = useState(offsetLocalIsoDate(-6));
  const [toDate, setToDate] = useState(localIsoDate());
  const [data, setData] = useState<FloorDashboard | OwnerDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setError(null);
    try {
      const endpoint = isOwner
        ? `/dashboard/summary?from_date=${fromDate}&to_date=${toDate}`
        : `/dashboard/floor?from_date=${fromDate}&to_date=${toDate}`;
      const resp = await apiRequest<OwnerDashboard | FloorDashboard>(endpoint);
      setData(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, [fromDate, toDate, isOwner]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const dismissAlert = async (id: number) => {
    await apiRequest(`/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "DISMISSED" }),
    });
    await loadDashboard();
  };

  const selectPresetRange = (mode: "weekly" | "monthly") => {
    setRangeMode(mode);
    setFromDate(offsetLocalIsoDate(mode === "weekly" ? -6 : -29));
    setToDate(localIsoDate());
  };

  const ownerFin = data && "financials" in data ? data.financials : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-amber-600" />
            Shed Overview &amp; Output Dashboard
          </h1>
          <p className="text-xs text-slate-500">
            Active dates: <b>{formatDateDMY(fromDate)}</b> to <b>{formatDateDMY(toDate)}</b> — cloth woven, loom speed check, alerts &amp; money summary.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => selectPresetRange("weekly")}
            className={`px-3 py-1.5 rounded-lg border font-semibold cursor-pointer transition ${
              rangeMode === "weekly"
                ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            Weekly (7d)
          </button>
          <button
            type="button"
            onClick={() => selectPresetRange("monthly")}
            className={`px-3 py-1.5 rounded-lg border font-semibold cursor-pointer transition ${
              rangeMode === "monthly"
                ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            Monthly (30d)
          </button>
          <div className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-lg border border-slate-300">
            <span className="text-[11px] font-semibold text-slate-500">From</span>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => {
                setRangeMode("custom");
                setFromDate(e.target.value);
              }}
              className="px-1.5 py-0.5 rounded text-xs font-medium focus:outline-none"
            />
            <span className="text-slate-400">to</span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => {
                setRangeMode("custom");
                setToDate(e.target.value);
              }}
              className="px-1.5 py-0.5 rounded text-xs font-medium focus:outline-none"
            />
          </div>
        </div>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}

      {data && (
        <>
          {/* Operational Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500">Today ({formatDateDMY(data.today_date)})</div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.today_metres} m</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {data.active_looms_count} / {data.operational_looms_count} shuttle looms active
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500">
                {rangeMode === "weekly" ? "Weekly Output" : rangeMode === "monthly" ? "Monthly Output" : "Period Output"}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.period_metres} m</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {data.total_downtime_mins > 0
                  ? `${formatHoursFromMins(data.total_downtime_mins)} hrs stopped across shifts`
                  : "All logged shifts ran"}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-amber-600" /> Active Warp Beams
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.running_beams_count}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                Yarn rolls currently weaving on looms
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" /> Open Shed Alerts
              </div>
              <div className={`text-2xl font-bold mt-0.5 ${data.open_alerts.length > 0 ? "text-rose-600" : "text-emerald-700"}`}>
                {data.open_alerts.length}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">Rate cuts &amp; yarn wastage alerts</div>
            </div>
          </div>

          {/* Machine Running & Speed Check (Plain-English Efficiency) */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-amber-600" />
                Machine Running &amp; Weaving Speed Efficiency
              </h2>
              <span
                className={`px-2.5 py-0.5 rounded text-[11px] font-bold ${
                  data.quality_recorded ? "bg-emerald-100 text-emerald-800" : "bg-blue-100 text-blue-800"
                }`}
              >
                {data.quality_recorded
                  ? "MACHINE + CLOTH QUALITY ACTIVE"
                  : "RUNNING & SPEED ONLY · DEFECT CHECK PENDING"}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">Time Run % (Availability)</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.availability_pct !== null ? `${data.availability_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {formatHoursFromMins(data.total_operating_mins)} out of {formatHoursFromMins(data.total_planned_mins)} shift hrs ran
                </div>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">Weaving Speed % (Performance)</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.performance_pct !== null ? `${data.performance_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Target speed: {data.total_ideal_metres} m (at RPM &amp; Pick)
                </div>
              </div>

              <div className="bg-amber-50 p-3 rounded-lg border border-amber-200">
                <div className="text-amber-900 font-semibold">Combined Efficiency %</div>
                <div className="text-lg font-bold text-amber-900 mt-0.5">
                  {data.utilization_ap_pct !== null ? `${data.utilization_ap_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-amber-800 mt-0.5">Overall loom output score</div>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">Defect-Free Cloth % (Quality)</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.quality_recorded && data.full_oee_pct !== null
                    ? `${data.quality_pct}% · OEE ${data.full_oee_pct}%`
                    : "No Defects Logged Yet"}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {data.quality_recorded
                    ? `Defective: ${data.confirmed_defective_metres} m`
                    : "Enter damaged metres in Daily Shift to unlock"}
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-600">{data.oee_note}</p>
          </div>

          {/* Owner P&L & Cashflow Card */}
          {ownerFin && (
            <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <IndianRupee className="w-4 h-4 text-emerald-700" />
                Owner Money Summary ({formatDateDMY(data.period_start)} to {formatDateDMY(data.period_end)})
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                  <div className="text-emerald-800">Billed Delivery Income</div>
                  <div className="text-lg font-bold text-emerald-900">
                    {formatRupeesFromPaise(ownerFin.billed_revenue_paise)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50">
                  <div className="text-slate-600">Wages + EB + Expenses</div>
                  <div className="text-lg font-bold text-slate-900">
                    {formatRupeesFromPaise(
                      ownerFin.finalized_wages_paise + ownerFin.eb_bills_paise + ownerFin.expenses_paise
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Wages: {formatRupeesFromPaise(ownerFin.finalized_wages_paise)} · EB:{" "}
                    {formatRupeesFromPaise(ownerFin.eb_bills_paise)} · Exp:{" "}
                    {formatRupeesFromPaise(ownerFin.expenses_paise)}
                  </div>
                  {ownerFin.eb_bills_paise === 0 && (
                    <div className="text-[10px] text-amber-700 mt-0.5">
                      No bi-monthly EB bill closed inside these dates.
                    </div>
                  )}
                </div>
                <div className="p-3 rounded-lg bg-slate-900 text-white">
                  <div className="text-slate-300">Net Operating Balance</div>
                  <div className="text-lg font-bold text-amber-400">
                    {formatRupeesFromPaise(ownerFin.net_operating_paise)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50">
                  <div className="text-slate-600">Pending Trader Balance (All-Time)</div>
                  <div className="text-lg font-bold text-slate-900">
                    {formatRupeesFromPaise(ownerFin.total_receivable_paise)}
                  </div>
                  {ownerFin.total_rate_underpayment_paise > 0 && (
                    <div className="text-[11px] text-rose-700 font-bold">
                      Rate-Cut Loss: {formatRupeesFromPaise(ownerFin.total_rate_underpayment_paise)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Open Alerts Center */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-amber-600" /> Active Alerts ({data.open_alerts.length})
            </h2>
            {data.open_alerts.length === 0 ? (
              <div className="text-xs text-emerald-700 flex items-center gap-1.5 py-2">
                <CheckCircle2 className="w-4 h-4" /> All clear — no open rate cuts or wastage alerts.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {data.open_alerts.map((a) => (
                  <div key={a.id} className="py-2 flex items-center justify-between gap-2 text-xs">
                    <span>
                      <span
                        className={`px-1.5 py-0.5 rounded font-bold mr-2 ${
                          a.severity === "CRITICAL" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {a.alert_type}
                      </span>
                      {a.message}
                    </span>
                    <button
                      type="button"
                      onClick={() => void dismissAlert(a.id)}
                      className="text-slate-500 underline shrink-0"
                    >
                      Dismiss
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Per-Loom Performance Table */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 overflow-x-auto space-y-2">
            <h2 className="text-sm font-bold">
              Per-Loom Breakdown ({formatDateDMY(fromDate)} to {formatDateDMY(toDate)})
            </h2>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Shuttle Loom</th>
                  <th className="py-2 pr-3">Fabric Sort</th>
                  <th className="py-2 pr-3">Shifts</th>
                  <th className="py-2 pr-3">Woven</th>
                  <th className="py-2 pr-3">Target Speed (m)</th>
                  <th className="py-2 pr-3">Time Run %</th>
                  <th className="py-2 pr-3">Speed %</th>
                  <th className="py-2">Efficiency %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.loom_breakdown.map((row) => (
                  <tr key={row.loom_id}>
                    <td className="py-1.5 pr-3 font-bold">
                      {row.loom_number}{" "}
                      <span className="text-slate-400 font-normal">({row.rated_rpm} RPM)</span>
                    </td>
                    <td className="py-1.5 pr-3">{row.sort_name ?? "No beam assigned"}</td>
                    <td className="py-1.5 pr-3">{row.shifts_logged}</td>
                    <td className="py-1.5 pr-3 font-semibold">{row.net_metres} m</td>
                    <td className="py-1.5 pr-3">{row.ideal_metres ? `${row.ideal_metres} m` : "-"}</td>
                    <td className="py-1.5 pr-3">{row.availability_pct !== null ? `${row.availability_pct}%` : "-"}</td>
                    <td className="py-1.5 pr-3">{row.performance_pct !== null ? `${row.performance_pct}%` : "-"}</td>
                    <td className="py-1.5 font-bold text-amber-700">
                      {row.utilization_ap_pct !== null ? `${row.utilization_ap_pct}%` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, BarChart3, Camera, CheckCircle2, ClipboardCheck, Gauge, IndianRupee, Layers, Truck, Zap } from "lucide-react";
import { apiRequest, formatDateDMY, formatHoursFromMins, formatRupeesFromPaise, localIsoDate, offsetLocalIsoDate } from "../api/client";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useLiveRefresh } from "../hooks/useLiveRefresh";
import { FloorDashboard, OwnerDashboard } from "../types/api";

export function DashboardPage() {
  const { user, tr } = useAuth();
  const toast = useToast();
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
      setError(err instanceof Error ? err.message : tr("Failed to load dashboard", "முகப்பு தகவலை ஏற்ற முடியவில்லை"));
    }
  }, [fromDate, toDate, isOwner, tr]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useLiveRefresh(loadDashboard);

  const dismissAlert = async (id: number) => {
    try {
      await apiRequest(`/alerts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "DISMISSED" }),
      });
      toast.success(tr("Alert dismissed.", "எச்சரிக்கை நீக்கப்பட்டது."));
      await loadDashboard();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tr("Could not dismiss alert", "எச்சரிக்கையை நீக்க முடியவில்லை"));
    }
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
            {tr("Shed Overview & Output Dashboard", "ஆலை சுருக்கம் & உற்பத்தி முகப்பு")}
          </h1>
          <p className="text-xs text-slate-500">
            {tr("Active dates", "தேதி வரம்பு")}: <b>{formatDateDMY(fromDate)}</b> {tr("to", "முதல்")} <b>{formatDateDMY(toDate)}</b>{" "}
            {tr("— cloth woven, loom speed check, alerts & money summary.", "வரை — நெய்த துணி, தறி வேகம், எச்சரிக்கைகள் & வரவு-செலவு.")}
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
            {tr("Weekly (7d)", "வாரம் (7 நாட்கள்)")}
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
            {tr("Monthly (30d)", "மாதம் (30 நாட்கள்)")}
          </button>
          <div className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-lg border border-slate-300">
            <span className="text-[11px] font-semibold text-slate-500">{tr("From", "முதல்")}</span>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => {
                setRangeMode("custom");
                setFromDate(e.target.value);
              }}
              className="px-1.5 py-0.5 rounded text-xs font-medium focus:outline-none"
            />
            <span className="text-slate-400">{tr("to", "வரை")}</span>
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

      <PageGuideBanner
        tip={tr(
          "Start here each day to check cloth woven, open alerts, and shed profit. Use the quick buttons below to jump straight to daily work.",
          "தினமும் இங்கிருந்து நெய்த துணி, எச்சரிக்கைகள் மற்றும் ஆலை லாபத்தைச் சரிபார்க்கவும். கீழே உள்ள விரைவு பட்டன்களைப் பயன்படுத்தவும்."
        )}
      />

      {/* Quick Actions Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
        <Link
          to="/today"
          className="flex items-center gap-2.5 p-3 rounded-xl bg-amber-500 text-slate-950 font-bold text-sm hover:bg-amber-400 transition shadow-sm"
        >
          <ClipboardCheck className="w-4 h-4 shrink-0" />
          <span>{tr("+ Log Today's Shift", "+ இன்றைய ஷிப்ட் பதிவு")}</span>
        </Link>
        <Link
          to="/analytics?tab=eb"
          className="flex items-center gap-2.5 p-3 rounded-xl bg-white border border-slate-200 text-slate-800 font-semibold text-sm hover:border-amber-400 hover:bg-amber-50/40 transition"
        >
          <Zap className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{tr("EB Bill Calculator", "EB பில் கணக்கீடு")}</span>
        </Link>
        {isOwner ? (
          <Link
            to="/deliveries"
            className="flex items-center gap-2.5 p-3 rounded-xl bg-white border border-slate-200 text-slate-800 font-semibold text-sm hover:border-amber-400 hover:bg-amber-50/40 transition"
          >
            <Truck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{tr("+ Delivery / EB Bill", "+ டெலிவரி / EB பில்")}</span>
          </Link>
        ) : (
          <Link
            to="/beams"
            className="flex items-center gap-2.5 p-3 rounded-xl bg-white border border-slate-200 text-slate-800 font-semibold text-sm hover:border-amber-400 hover:bg-amber-50/40 transition"
          >
            <Layers className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{tr("Beams & Yarn", "பீம் & நூல்")}</span>
          </Link>
        )}
        <Link
          to="/inspect"
          className="flex items-center gap-2.5 p-3 rounded-xl bg-white border border-slate-200 text-slate-800 font-semibold text-sm hover:border-amber-400 hover:bg-amber-50/40 transition"
        >
          <Camera className="w-4 h-4 text-indigo-600 shrink-0" />
          <span>{tr("Check Cloth Photo", "துணி குறைபாடு ஆய்வு")}</span>
        </Link>
      </div>

      {data && (
        <>
          {/* Operational Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500">
                {tr("Today", "இன்று")} ({formatDateDMY(data.today_date)})
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.today_metres} m</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {tr(
                  `${data.active_looms_count} / ${data.operational_looms_count} shuttle looms active`,
                  `${data.active_looms_count} / ${data.operational_looms_count} தறிகள் இயங்குகின்றன`
                )}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500">
                {rangeMode === "weekly"
                  ? tr("Weekly Output", "வார உற்பத்தி")
                  : rangeMode === "monthly"
                    ? tr("Monthly Output", "மாத உற்பத்தி")
                    : tr("Period Output", "கால உற்பத்தி")}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.period_metres} m</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {data.total_downtime_mins > 0
                  ? tr(
                      `${formatHoursFromMins(data.total_downtime_mins)} hrs stopped across shifts`,
                      `ஷிப்டுகளில் ${formatHoursFromMins(data.total_downtime_mins)} மணி நிறுத்தம்`
                    )
                  : tr("All logged shifts ran", "பதிவு செய்த அனைத்து ஷிப்டுகளும் ஓடின")}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-amber-600" /> {tr("Active Warp Beams", "ஓடும் பாவு பீம்கள்")}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">{data.running_beams_count}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {tr("Yarn rolls currently weaving on looms", "தற்போது தறிகளில் ஓடும் பீம்கள்")}
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-xs text-slate-500 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" /> {tr("Open Shed Alerts", "திறந்த எச்சரிக்கைகள்")}
              </div>
              <div className={`text-2xl font-bold mt-0.5 ${data.open_alerts.length > 0 ? "text-rose-600" : "text-emerald-700"}`}>
                {data.open_alerts.length}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">{tr("Rate cuts & yarn wastage alerts", "விலை குறைப்பு & நூல் வீண் எச்சரிக்கைகள்")}</div>
            </div>
          </div>

          {/* Machine Running & Speed Check */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-amber-600" />
                {tr("Machine Running & Weaving Speed Efficiency", "இயந்திர இயக்கம் & நெசவு வேகத் திறன்")}
              </h2>
              <span
                className={`px-2.5 py-0.5 rounded text-[11px] font-bold ${
                  data.quality_recorded ? "bg-emerald-100 text-emerald-800" : "bg-blue-100 text-blue-800"
                }`}
              >
                {data.quality_recorded
                  ? tr("MACHINE + CLOTH QUALITY ACTIVE", "இயந்திரம் + துணி தரம் செயலில்")
                  : tr("RUNNING & SPEED ONLY · DEFECT CHECK PENDING", "இயக்கம் & வேகம் மட்டும் · குறைபாடு பதிவு இல்லை")}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">{tr("Time Run % (Availability)", "இயங்கிய நேரம் %")}</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.availability_pct !== null ? `${data.availability_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {tr(
                    `${formatHoursFromMins(data.total_operating_mins)} out of ${formatHoursFromMins(data.total_planned_mins)} shift hrs ran`,
                    `${formatHoursFromMins(data.total_planned_mins)} மணி ஷிப்டில் ${formatHoursFromMins(data.total_operating_mins)} மணி ஓடியது`
                  )}
                </div>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">{tr("Weaving Speed % (Performance)", "நெசவு வேகம் %")}</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.performance_pct !== null ? `${data.performance_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {tr(`Target speed: ${data.total_ideal_metres} m (at RPM & Pick)`, `இலக்கு: ${data.total_ideal_metres} மீ (RPM & பிக்)`)}
                </div>
              </div>

              <div className="bg-amber-50 p-3 rounded-lg border border-amber-200">
                <div className="text-amber-900 font-semibold">{tr("Combined Efficiency %", "மொத்த தறி திறன் %")}</div>
                <div className="text-lg font-bold text-amber-900 mt-0.5">
                  {data.utilization_ap_pct !== null ? `${data.utilization_ap_pct}%` : "N/A"}
                </div>
                <div className="text-[11px] text-amber-800 mt-0.5">{tr("Overall loom output score", "ஒட்டுமொத்த உற்பத்தி மதிப்பீடு")}</div>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-600 font-semibold">{tr("Defect-Free Cloth % (Quality)", "குறைபாடற்ற துணி % (தரம்)")}</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5">
                  {data.quality_recorded && data.full_oee_pct !== null
                    ? `${data.quality_pct}% · OEE ${data.full_oee_pct}%`
                    : tr("No Defects Logged Yet", "குறைபாடு பதிவு இல்லை")}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {data.quality_recorded
                    ? tr(`Defective: ${data.confirmed_defective_metres} m`, `சேதமானது: ${data.confirmed_defective_metres} மீ`)
                    : tr("Enter damaged metres in Daily Shift to unlock", "தினசரி ஷிப்டில் சேத மீட்டரை பதிந்தால் காட்டும்")}
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
                {tr("Owner Money Summary", "உரிமையாளர் வரவு-செலவு சுருக்கம்")} ({formatDateDMY(data.period_start)} – {formatDateDMY(data.period_end)})
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                  <div className="text-emerald-800">{tr("Billed Delivery Income", "டெலிவரி வருமானம்")}</div>
                  <div className="text-lg font-bold text-emerald-900">
                    {formatRupeesFromPaise(ownerFin.billed_revenue_paise)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50">
                  <div className="text-slate-600">{tr("Wages + EB + Expenses", "கூலி + EB + செலவுகள்")}</div>
                  <div className="text-lg font-bold text-slate-900">
                    {formatRupeesFromPaise(
                      ownerFin.finalized_wages_paise + ownerFin.eb_bills_paise + ownerFin.expenses_paise
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {tr("Wages", "கூலி")}: {formatRupeesFromPaise(ownerFin.finalized_wages_paise)} · EB:{" "}
                    {formatRupeesFromPaise(ownerFin.eb_bills_paise)} · {tr("Exp", "செலவு")}:{" "}
                    {formatRupeesFromPaise(ownerFin.expenses_paise)}
                  </div>
                  {ownerFin.eb_bills_paise === 0 && (
                    <div className="text-[10px] text-amber-700 mt-0.5">
                      {tr("No bi-monthly EB bill closed inside these dates.", "இந்த தேதிகளில் EB பில் ஏதும் இல்லை.")}
                    </div>
                  )}
                </div>
                <div className="p-3 rounded-lg bg-slate-900 text-white">
                  <div className="text-slate-300">{tr("Net Operating Balance", "நிகர இருப்பு (லாபம்)")}</div>
                  <div className="text-lg font-bold text-amber-400">
                    {formatRupeesFromPaise(ownerFin.net_operating_paise)}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50">
                  <div className="text-slate-600">{tr("Pending Trader Balance (All-Time)", "வியாபாரிகள் பாக்கி (மொத்தம்)")}</div>
                  <div className="text-lg font-bold text-slate-900">
                    {formatRupeesFromPaise(ownerFin.total_receivable_paise)}
                  </div>
                  {ownerFin.total_rate_underpayment_paise > 0 && (
                    <div className="text-[11px] text-rose-700 font-bold">
                      {tr("Rate-Cut Loss", "விலை குறைப்பு இழப்பு")}: {formatRupeesFromPaise(ownerFin.total_rate_underpayment_paise)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Open Alerts Center */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-amber-600" /> {tr(`Active Alerts (${data.open_alerts.length})`, `செயலில் உள்ள எச்சரிக்கைகள் (${data.open_alerts.length})`)}
            </h2>
            {data.open_alerts.length === 0 ? (
              <div className="text-xs text-emerald-700 flex items-center gap-1.5 py-2">
                <CheckCircle2 className="w-4 h-4" />{" "}
                {tr("All clear — no open rate cuts or wastage alerts.", "எல்லாம் சீராக உள்ளது — எச்சரிக்கைகள் இல்லை.")}
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
                      {tr("Dismiss", "நீக்கு")}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Per-Loom Performance Table */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 overflow-x-auto space-y-2">
            <h2 className="text-sm font-bold">
              {tr("Per-Loom Breakdown", "ஒவ்வொரு தறியின் விவரம்")} ({formatDateDMY(fromDate)} – {formatDateDMY(toDate)})
            </h2>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">{tr("Shuttle Loom", "தறி")}</th>
                  <th className="py-2 pr-3">{tr("Fabric Sort", "துணி வகை")}</th>
                  <th className="py-2 pr-3">{tr("Shifts", "ஷிப்டுகள்")}</th>
                  <th className="py-2 pr-3">{tr("Woven", "நெய்தது")}</th>
                  <th className="py-2 pr-3">{tr("Target Speed (m)", "இலக்கு (மீ)")}</th>
                  <th className="py-2 pr-3">{tr("Time Run %", "நேரம் %")}</th>
                  <th className="py-2 pr-3">{tr("Speed %", "வேகம் %")}</th>
                  <th className="py-2">{tr("Efficiency %", "திறன் %")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.loom_breakdown.map((row) => (
                  <tr key={row.loom_id}>
                    <td className="py-1.5 pr-3 font-bold">
                      {row.loom_number}{" "}
                      <span className="text-slate-400 font-normal">({row.rated_rpm} RPM)</span>
                    </td>
                    <td className="py-1.5 pr-3">{row.sort_name ?? tr("No beam assigned", "பீம் இல்லை")}</td>
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

import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Calculator, CalendarClock, FileSpreadsheet, Printer, TrendingUp, Zap } from "lucide-react";
import { apiRequest, downloadProtectedFile, formatDateDMY, formatRupeesFromPaise } from "../api/client";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { TechnicalDetailsToggle } from "../components/TechnicalDetailsToggle";
import { useAuth } from "../context/AuthContext";
import { Trader } from "../types/api";

interface BeamEtaRow {
  beam_id: number;
  beam_no: string;
  sort_name: string;
  loom_number: string;
  remaining_m: number;
  p50_daily_m: number;
  p75_daily_m: number;
  p25_daily_m: number;
  working_days_left_p50: number;
  eta_date_p50: string;
  eta_date_p75: string;
  eta_date_p25: string;
  due_date: string | null;
  days_variance: number | null;
  on_track: boolean;
}

interface EbEfficiencyPeriod {
  bill_id: number;
  period_start: string;
  period_end: string;
  days: number;
  units_kwh: number;
  net_bill_paise: number;
  metres_produced: number;
  metres_source: string;
  kwh_per_metre: number | null;
  metres_per_kwh: number | null;
  eb_paise_per_metre: number | null;
  status_flag: string;
  status_note: string;
}

interface EbCalcSlabRow {
  slab_no: number;
  from_unit: number;
  to_unit: number | null;
  units_in_slab: number;
  rate_paise_per_unit: number;
  amount_paise: number;
}

interface EbCalcResult {
  tariff_name: string;
  units_kwh: number;
  sanctioned_kw: number;
  recorded_demand_kw: number | null;
  billing_days: number;
  free_quota_applied: boolean;
  slabs: EbCalcSlabRow[];
  energy_paise: number;
  fixed_paise: number;
  fppca_paise: number;
  tax_paise: number;
  net_bill_paise: number;
  rounded_payable_rupees: number;
  avg_paise_per_kwh: number;
}

interface AnalyticsOverview {
  beam_etas: BeamEtaRow[];
  eb_prediction: {
    tariff_name: string;
    sanctioned_kw: number;
    billing_cycle_days: number;
    projected_units_kwh: number;
    energy_paise: number;
    fixed_paise: number;
    tax_paise: number;
    fppca_paise: number;
    projected_net_bill_paise: number;
    slab_note: string;
    outage_30d_stopped_mins: number;
    outage_30d_stopped_hrs: string;
    outage_30d_lost_metres: number;
    outage_30d_lost_revenue_paise: number;
  };
  eb_efficiency?: {
    periods: EbEfficiencyPeriod[];
    avg_kwh_per_metre: number | null;
    avg_metres_per_kwh: number | null;
    avg_eb_paise_per_metre: number | null;
    baseline_kwh_per_metre: number;
    model_kind: string;
    base_kwh: number;
    slope_kwh_per_metre: number;
    sample_estimates: {
      metres: number;
      estimated_kwh: number;
      estimated_bill_paise: number;
      eb_paise_per_metre: number;
    }[];
  };
  anomalies: {
    shift_id: number;
    entry_date: string;
    shift_no: number;
    loom_number: string;
    net_metres: number;
    expected_median_m: number;
    kind: string;
    severity: string;
    reason: string;
  }[];
  weekly_forecast: {
    history: {
      label: string;
      week_start: string;
      week_end: string;
      actual_metres: number;
      loom_shifts: number;
      metres_per_shift: number;
    }[];
    models: {
      model: string;
      mae_m: number;
      mape_pct: number;
      next_week_forecast_m: number;
      is_winner: boolean;
    }[];
    winner_model: string;
    recommended_forecast_m: number;
    next_week_start: string;
    next_week_end: string;
    planned_working_days: number;
    planned_loom_shifts: number;
  };
}

interface StatementData {
  unit_name: string;
  location: string;
  period_start: string;
  period_end: string;
  period_metres: string;
  availability_pct: number | null;
  performance_pct: number | null;
  utilization_ap_pct: number | null;
  quality_pct: number | null;
  financials: {
    billed_revenue_paise: number;
    finalized_wages_paise: number;
    eb_bills_paise: number;
    expenses_paise: number;
    net_operating_paise: number;
    total_receivable_paise: number;
    total_rate_underpayment_paise: number;
  };
  deliveries: { challan_no: string; delivery_date: string; trader_name: string; total_metres: string; amount_paise: number }[];
  payments: { payment_date: string; trader_name: string; reference: string; amount_paise: number; shortage_deduction_paise: number }[];
}

interface ScenarioMetrics {
  loom_count: number;
  monthly_metres: number;
  gross_revenue_paise: number;
  weaver_wages_paise: number;
  helper_wages_paise: number;
  eb_monthly_paise: number;
  overhead_paise: number;
  ebitda_paise: number;
  total_capex_paise: number;
  emi_paise: number;
  net_after_emi_paise: number;
  payback_months: number | null;
}

interface ExpansionSimResult {
  inputs: Record<string, number>;
  primary: ScenarioMetrics;
  presets: ScenarioMetrics[];
  sensitivity_efficiencies: number[];
  sensitivity_matrix: { rate_rs: number; cells: { efficiency_pct: number; ebitda_paise: number }[] }[];
}

export function AnalyticsReportsPage() {
  const { user } = useAuth();
  const isOwner = user?.role === "OWNER";
  const [searchParams, setSearchParams] = useSearchParams();

  const rawTab = searchParams.get("tab");
  const tab: "forecast" | "eb" | "reports" | "simulator" =
    rawTab === "eb"
      ? "eb"
      : rawTab === "reports" && isOwner
        ? "reports"
        : rawTab === "simulator" && isOwner
          ? "simulator"
          : "forecast";

  const setTab = (next: "forecast" | "eb" | "reports" | "simulator") => {
    setSearchParams({ tab: next }, { replace: true });
  };

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [statement, setStatement] = useState<StatementData | null>(null);
  const [traders, setTraders] = useState<Trader[]>([]);
  const [stmtTraderId, setStmtTraderId] = useState<string>("");
  const [simResult, setSimResult] = useState<ExpansionSimResult | null>(null);

  const [simLooms, setSimLooms] = useState(20);
  const [simRpm, setSimRpm] = useState(160);
  const [simEff, setSimEff] = useState(85);
  const [simRate, setSimRate] = useState("6.00");
  const [simCapex, setSimCapex] = useState("95000");
  const [simLoanPct, setSimLoanPct] = useState(70);

  const [calcMode, setCalcMode] = useState<"units" | "readings" | "metres">("units");
  const [calcUnits, setCalcUnits] = useState("6361");
  const [calcPrevRead, setCalcPrevRead] = useState("524659");
  const [calcCurrRead, setCalcCurrRead] = useState("531020");
  const [calcFabricMetres, setCalcFabricMetres] = useState("50000");
  const [calcKwhPerMetre, setCalcKwhPerMetre] = useState("0.131");
  const [calcClothRateRs, setCalcClothRateRs] = useState("6.00");
  const [calcOptMetres, setCalcOptMetres] = useState("");
  const [calcKw, setCalcKw] = useState("10");
  const [calcDemandKw, setCalcDemandKw] = useState("");
  const [calcDays, setCalcDays] = useState("60");
  const [calcResult, setCalcResult] = useState<EbCalcResult | null>(null);
  const [calcActiveMetres, setCalcActiveMetres] = useState<number | null>(null);

  const [error, setError] = useState<string | null>(null);

  const runEbCalc = useCallback(
    async (opts?: { overrideUnits?: number; overrideMetres?: number; mode?: "units" | "readings" | "metres" }) => {
      const effectiveMode = opts?.mode ?? (opts?.overrideMetres !== undefined ? "metres" : opts?.overrideUnits !== undefined ? "units" : calcMode);
      const kwhRatio = Math.max(0.01, parseFloat(calcKwhPerMetre) || 0.131);
      let computedUnits = 0;
      let activeM: number | null = null;

      if (effectiveMode === "metres") {
        const mVal = opts?.overrideMetres !== undefined ? opts.overrideMetres : Math.max(0, parseFloat(calcFabricMetres) || 0);
        if (opts?.overrideMetres !== undefined) {
          setCalcMode("metres");
          setCalcFabricMetres(String(opts.overrideMetres));
        }
        computedUnits = Math.round(mVal * kwhRatio * 10) / 10;
        activeM = mVal > 0 ? mVal : null;
      } else if (effectiveMode === "readings") {
        computedUnits = Math.max(0, (parseFloat(calcCurrRead) || 0) - (parseFloat(calcPrevRead) || 0));
        const optM = parseFloat(calcOptMetres);
        activeM = optM > 0 ? optM : null;
      } else {
        computedUnits = opts?.overrideUnits !== undefined ? opts.overrideUnits : Math.max(0, parseFloat(calcUnits) || 0);
        if (opts?.overrideUnits !== undefined) {
          setCalcMode("units");
          setCalcUnits(String(opts.overrideUnits));
        }
        const optM = parseFloat(calcOptMetres);
        activeM = optM > 0 ? optM : null;
      }

      const params = new URLSearchParams({
        units_kwh: String(computedUnits),
        sanctioned_kw: String(parseFloat(calcKw) || 10),
        billing_days: String(parseInt(calcDays, 10) || 60),
      });
      if (calcDemandKw.trim() !== "" && parseFloat(calcDemandKw) > 0) {
        params.set("recorded_demand_kw", String(parseFloat(calcDemandKw)));
      }
      setError(null);
      try {
        const res = await apiRequest<EbCalcResult>(`/analytics/eb-calculate?${params.toString()}`);
        setCalcResult(res);
        setCalcActiveMetres(activeM);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to calculate EB bill");
      }
    },
    [calcMode, calcUnits, calcPrevRead, calcCurrRead, calcFabricMetres, calcKwhPerMetre, calcOptMetres, calcKw, calcDemandKw, calcDays]
  );

  const loadOverview = useCallback(async () => {
    setError(null);
    try {
      const ov = await apiRequest<AnalyticsOverview>("/analytics/overview");
      setOverview(ov);
      if (ov.eb_prediction?.sanctioned_kw) {
        setCalcKw(String(ov.eb_prediction.sanctioned_kw));
      }
      if (ov.eb_prediction?.billing_cycle_days) {
        setCalcDays(String(ov.eb_prediction.billing_cycle_days));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load shed analytics");
    }
  }, []);

  useEffect(() => {
    if (tab === "eb" && !calcResult) {
      void runEbCalc();
    }
  }, [tab, calcResult, runEbCalc]);

  const loadOwnerReports = useCallback(async () => {
    if (!isOwner) return;
    try {
      const qs = stmtTraderId ? `?trader_id=${stmtTraderId}` : "";
      const [st, tr, sim] = await Promise.all([
        apiRequest<StatementData>(`/analytics/reports/statement${qs}`),
        apiRequest<Trader[]>("/traders"),
        apiRequest<ExpansionSimResult>("/analytics/expansion-default"),
      ]);
      setStatement(st);
      setTraders(tr);
      setSimResult(sim);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    }
  }, [isOwner, stmtTraderId]);

  useEffect(() => {
    void loadOverview();
    void loadOwnerReports();
  }, [loadOverview, loadOwnerReports]);

  const runCustomSimulation = async (presetCount?: number) => {
    const countToUse = presetCount ?? simLooms;
    if (presetCount) setSimLooms(presetCount);
    setError(null);
    try {
      const res = await apiRequest<ExpansionSimResult>("/analytics/expansion-simulate", {
        method: "POST",
        body: JSON.stringify({
          loom_count: countToUse,
          rpm: simRpm,
          efficiency_pct: simEff,
          rate_per_metre_rs: parseFloat(simRate) || 6.0,
          capex_per_loom_rs: parseFloat(simCapex) || 95000,
          loan_pct: simLoanPct,
        }),
      });
      setSimResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    }
  };

  return (
    <div className="space-y-5 pb-10">
      <div className="no-print">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-amber-600" />
          Shed Analytics, Beam ETAs, Reports &amp; Simulator
        </h1>
        <p className="text-xs text-slate-500">
          Live Beam Finish ETAs, bi-monthly EB bill predictions, production anomaly alerts, Excel/Print statements, and expansion planning.
        </p>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm no-print">{error}</div>}

      <PageGuideBanner
        tip={
          tab === "eb"
            ? "Check any TNPDCL EB bill by Units, Meter Readings, or Fabric Metres woven — and compare past EB bills against cloth produced to spot meter issues."
            : tab === "reports"
              ? "Download your entire shed ledger as a 7-sheet Excel workbook or print a clean monthly account statement for any trader."
              : tab === "simulator"
                ? "Test what your monthly profit, EB bill, and loan payment would look like if you expand to 20, 30, 50, or 100 shuttle looms."
                : "See next week's expected cloth output, when each warp beam will finish, and any unusual loom drops — click 'Show' on the bottom card for thesis stats."
        }
      />

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2 no-print">
        <button
          type="button"
          onClick={() => setTab("forecast")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold cursor-pointer ${
            tab === "forecast" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
          }`}
        >
          1. Forecast, Beam ETA &amp; Anomalies
        </button>
        <button
          type="button"
          onClick={() => setTab("eb")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold cursor-pointer ${
            tab === "eb" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
          }`}
        >
          2. EB Bill &amp; Power Efficiency
        </button>
        {isOwner && (
          <>
            <button
              type="button"
              onClick={() => setTab("reports")}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold cursor-pointer ${
                tab === "reports" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
              }`}
            >
              3. Excel (.xlsx) &amp; Print Statements
            </button>
            <button
              type="button"
              onClick={() => setTab("simulator")}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold cursor-pointer ${
                tab === "simulator" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
              }`}
            >
              4. Loom Expansion Simulator (20–100 Looms)
            </button>
          </>
        )}
      </div>

      {/* Tab 1: Forecast, Beam ETA & Anomalies */}
      {tab === "forecast" && overview && (
        <div className="space-y-4">
          {/* Next Week Forecast — Clean Hero Summary */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold flex items-center gap-1.5 text-slate-900">
                  <TrendingUp className="w-4 h-4 text-amber-600" />
                  Next 7-Day Cloth Production Forecast
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {formatDateDMY(overview.weekly_forecast.next_week_start)} to{" "}
                  {formatDateDMY(overview.weekly_forecast.next_week_end)} ·{" "}
                  <b>{overview.weekly_forecast.planned_working_days}</b> working days (
                  <b>{overview.weekly_forecast.planned_loom_shifts}</b> planned loom-shifts)
                </p>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 text-right">
                <div className="text-[11px] font-semibold text-amber-800">Expected Next 7 Days</div>
                <div className="text-2xl font-extrabold text-amber-950">
                  {overview.weekly_forecast.recommended_forecast_m} m
                </div>
              </div>
            </div>

            <TechnicalDetailsToggle
              title="Show Forecast Model Backtest (CN-MA vs Holt vs Naive — Thesis Details)"
              subtitle={`Active winner: ${overview.weekly_forecast.winner_model} · 5-week walk-forward MAE & MAPE accuracy`}
            >
              <div className="grid md:grid-cols-2 gap-4 overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-1.5 pr-2">Week</th>
                      <th className="py-1.5 pr-2">Dates</th>
                      <th className="py-1.5 pr-2">Shifts</th>
                      <th className="py-1.5">Woven (m)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.weekly_forecast.history.map((w) => (
                      <tr key={w.label}>
                        <td className="py-1.5 pr-2 font-bold">{w.label}</td>
                        <td className="py-1.5 pr-2">
                          {formatDateDMY(w.week_start)} – {formatDateDMY(w.week_end)}
                        </td>
                        <td className="py-1.5 pr-2">{w.loom_shifts}</td>
                        <td className="py-1.5 font-semibold">{w.actual_metres} m</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <table className="w-full text-xs text-left">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-1.5 pr-2">Forecast Method</th>
                      <th className="py-1.5 pr-2">Backtest MAE</th>
                      <th className="py-1.5 pr-2">MAPE %</th>
                      <th className="py-1.5">Next 7d Target</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.weekly_forecast.models.map((m) => (
                      <tr key={m.model} className={m.is_winner ? "bg-emerald-50/60 font-semibold" : ""}>
                        <td className="py-1.5 pr-2">
                          {m.model} {m.is_winner && <span className="text-[10px] text-emerald-700">(Lowest Error)</span>}
                        </td>
                        <td className="py-1.5 pr-2">{m.mae_m} m</td>
                        <td className="py-1.5 pr-2">{m.mape_pct}%</td>
                        <td className="py-1.5">{m.next_week_forecast_m} m</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TechnicalDetailsToggle>
          </div>

          {/* Beam Finish ETA Table */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2 overflow-x-auto">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <CalendarClock className="w-4 h-4 text-amber-600" />
              When Will Each Warp Beam Finish? ({overview.beam_etas.length} Running)
            </h2>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-1.5 pr-2">Beam &amp; Loom</th>
                  <th className="py-1.5 pr-2">Cloth Left</th>
                  <th className="py-1.5 pr-2">Avg Daily Weaving</th>
                  <th className="py-1.5 pr-2">Expected Finish</th>
                  <th className="py-1.5 pr-2">Target Due</th>
                  <th className="py-1.5">On Time?</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {overview.beam_etas.map((b) => (
                  <tr key={b.beam_id}>
                    <td className="py-1.5 pr-2 font-bold">
                      {b.beam_no} <span className="font-normal text-slate-500">({b.loom_number})</span>
                    </td>
                    <td className="py-1.5 pr-2">{b.remaining_m} m</td>
                    <td className="py-1.5 pr-2">
                      <b>{b.p50_daily_m} m/day</b>{" "}
                      <span className="text-[10px] text-slate-400">
                        ({b.p25_daily_m}–{b.p75_daily_m})
                      </span>
                    </td>
                    <td className="py-1.5 pr-2 font-semibold">
                      {formatDateDMY(b.eta_date_p50)} ({b.working_days_left_p50} work days)
                    </td>
                    <td className="py-1.5 pr-2">{b.due_date ? formatDateDMY(b.due_date) : "-"}</td>
                    <td className="py-1.5">
                      {b.due_date ? (
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            b.on_track ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {b.on_track ? `On Track (${b.days_variance}d early)` : `Late (${b.days_variance}d)`}
                        </span>
                      ) : (
                        <span className="text-slate-400">No due date</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Anomalies */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
            <h2 className="text-sm font-bold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              Unusual Loom Drops &amp; Speed Alerts (Last 30 Days — {overview.anomalies.length})
            </h2>
            {overview.anomalies.length === 0 ? (
              <div className="text-xs text-emerald-700">All looms ran normally with no unusual output spikes or sudden drops in the past 30 days.</div>
            ) : (
              <div className="divide-y divide-slate-100 text-xs">
                {overview.anomalies.map((a) => (
                  <div key={a.shift_id} className="py-2 flex flex-wrap justify-between gap-2">
                    <span>
                      <span
                        className={`px-1.5 py-0.5 rounded font-bold mr-2 ${
                          a.severity === "CRITICAL" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {a.kind === "PHYSICAL_CAP" ? "Speed Check" : "Low Output"}
                      </span>
                      <b>{a.loom_number}</b> on {formatDateDMY(a.entry_date)} (Shift {a.shift_no}): {a.reason}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: EB Predictor, Power Efficiency & Outage Loss */}
      {tab === "eb" && overview && (
        <div className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-600" />
                Next Bi-Monthly EB Bill Predictor ({overview.eb_prediction.billing_cycle_days}-Day Cycle)
              </h2>
              <p className="text-xs text-slate-500">
                Tariff: <b>{overview.eb_prediction.tariff_name}</b> · Load {overview.eb_prediction.sanctioned_kw} kW ·{" "}
                {overview.eb_prediction.slab_note}
              </p>
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div className="bg-slate-50 p-3 rounded-lg">
                  <div className="text-slate-500">Projected Units</div>
                  <div className="text-lg font-bold">{overview.eb_prediction.projected_units_kwh} kWh</div>
                </div>
                <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                  <div className="text-amber-900">Estimated Total Bill</div>
                  <div className="text-lg font-bold text-amber-900">
                    {formatRupeesFromPaise(overview.eb_prediction.projected_net_bill_paise)}
                  </div>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg">
                  Energy Slab Charge: <b>{formatRupeesFromPaise(overview.eb_prediction.energy_paise)}</b>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg">
                  Fixed + FPPCA + Tax:{" "}
                  <b>
                    {formatRupeesFromPaise(
                      overview.eb_prediction.fixed_paise +
                        overview.eb_prediction.fppca_paise +
                        overview.eb_prediction.tax_paise
                    )}
                  </b>
                </div>
              </div>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
              <h2 className="text-sm font-bold">30-Day Stoppage &amp; Power-Outage Opportunity Loss</h2>
              <div className="grid grid-cols-3 gap-2.5 text-xs">
                <div className="bg-slate-50 p-3 rounded-lg">
                  <div className="text-slate-500">Stopped Time</div>
                  <div className="text-lg font-bold">{overview.eb_prediction.outage_30d_stopped_hrs} hrs</div>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <div className="text-slate-500">Est. Lost Cloth</div>
                  <div className="text-lg font-bold">{overview.eb_prediction.outage_30d_lost_metres} m</div>
                </div>
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-lg">
                  <div className="text-rose-800">Est. Lost Revenue</div>
                  <div className="text-lg font-bold text-rose-800">
                    {formatRupeesFromPaise(overview.eb_prediction.outage_30d_lost_revenue_paise)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive TNPDCL EB Bill Calculator */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold flex items-center gap-1.5">
                  <Calculator className="w-4 h-4 text-amber-600" />
                  TNPDCL EB Bill Calculator (Live Slab Working Sheet)
                </h2>
                <p className="text-xs text-slate-500">
                  Uses your active tariff plan ({overview.eb_prediction.tariff_name}). Enter total kWh or meter readings to verify any EB bill down to the rupee.
                </p>
              </div>
              <div className="flex flex-wrap rounded-lg border border-slate-200 overflow-hidden text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => {
                    setCalcMode("units");
                    void runEbCalc({ mode: "units" });
                  }}
                  className={`px-3 py-1.5 cursor-pointer ${
                    calcMode === "units" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  Total Units (kWh)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCalcMode("readings");
                    void runEbCalc({ mode: "readings" });
                  }}
                  className={`px-3 py-1.5 cursor-pointer ${
                    calcMode === "readings" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  EB Meter (Prev → Curr)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCalcMode("metres");
                    void runEbCalc({ mode: "metres" });
                  }}
                  className={`px-3 py-1.5 cursor-pointer ${
                    calcMode === "metres" ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  By Fabric Metres (m)
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-3 text-xs">
              {calcMode === "units" && (
                <>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Units Consumed (kWh)</label>
                    <input
                      type="number"
                      min={0}
                      step={1}
                      value={calcUnits}
                      onChange={(e) => setCalcUnits(e.target.value)}
                      aria-label="EB Calculator Units kWh"
                      className="w-32 border border-slate-300 rounded-lg px-2.5 py-1.5 font-semibold"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fabric Metres (m, opt.)</label>
                    <input
                      type="number"
                      min={0}
                      step={100}
                      placeholder="e.g. 49550"
                      value={calcOptMetres}
                      onChange={(e) => setCalcOptMetres(e.target.value)}
                      className="w-32 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                </>
              )}

              {calcMode === "readings" && (
                <>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Previous Reading (kWh)</label>
                    <input
                      type="number"
                      min={0}
                      value={calcPrevRead}
                      onChange={(e) => setCalcPrevRead(e.target.value)}
                      className="w-28 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Current Reading (kWh)</label>
                    <input
                      type="number"
                      min={0}
                      value={calcCurrRead}
                      onChange={(e) => setCalcCurrRead(e.target.value)}
                      className="w-28 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                  <div className="px-2.5 py-1.5 rounded-lg bg-slate-100 text-slate-700 font-semibold">
                    = {Math.max(0, (parseFloat(calcCurrRead) || 0) - (parseFloat(calcPrevRead) || 0)).toLocaleString("en-IN")} kWh
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fabric Metres (m, opt.)</label>
                    <input
                      type="number"
                      min={0}
                      step={100}
                      placeholder="e.g. 49550"
                      value={calcOptMetres}
                      onChange={(e) => setCalcOptMetres(e.target.value)}
                      className="w-28 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                </>
              )}

              {calcMode === "metres" && (
                <>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fabric Metres Produced (m)</label>
                    <input
                      type="number"
                      min={0}
                      step={500}
                      value={calcFabricMetres}
                      onChange={(e) => setCalcFabricMetres(e.target.value)}
                      aria-label="EB Calculator Fabric Metres"
                      className="w-36 border border-slate-300 rounded-lg px-2.5 py-1.5 font-semibold"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Power Rate (kWh / m)</label>
                    <input
                      type="number"
                      min={0.01}
                      max={2}
                      step={0.005}
                      value={calcKwhPerMetre}
                      onChange={(e) => setCalcKwhPerMetre(e.target.value)}
                      className="w-24 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Job Rate (₹ / m)</label>
                    <input
                      type="number"
                      min={0.5}
                      step={0.25}
                      value={calcClothRateRs}
                      onChange={(e) => setCalcClothRateRs(e.target.value)}
                      className="w-20 border border-slate-300 rounded-lg px-2.5 py-1.5"
                    />
                  </div>
                  <div className="px-2.5 py-1.5 rounded-lg bg-slate-100 text-slate-700 font-semibold">
                    ≈ {Math.round((parseFloat(calcFabricMetres) || 0) * (parseFloat(calcKwhPerMetre) || 0.131)).toLocaleString("en-IN")} kWh
                  </div>
                </>
              )}

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Sanctioned Load (kW)</label>
                <input
                  type="number"
                  min={1}
                  step={0.5}
                  value={calcKw}
                  onChange={(e) => setCalcKw(e.target.value)}
                  className="w-24 border border-slate-300 rounded-lg px-2.5 py-1.5"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Recorded Demand (kW, opt.)</label>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  placeholder="Auto"
                  value={calcDemandKw}
                  onChange={(e) => setCalcDemandKw(e.target.value)}
                  className="w-28 border border-slate-300 rounded-lg px-2.5 py-1.5"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Cycle Days</label>
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={calcDays}
                  onChange={(e) => setCalcDays(e.target.value)}
                  className="w-20 border border-slate-300 rounded-lg px-2.5 py-1.5"
                />
              </div>
              <button
                type="button"
                onClick={() => void runEbCalc()}
                className="px-4 py-1.5 rounded-lg bg-amber-500 text-slate-950 font-bold hover:bg-amber-400 cursor-pointer"
              >
                Calculate EB Bill
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <span className="text-slate-500 font-medium">Quick Test:</span>
              {calcMode === "metres"
                ? [30000, 40000, 50000, 55000, 60000].map((mVal) => (
                    <button
                      key={mVal}
                      type="button"
                      onClick={() => void runEbCalc({ overrideMetres: mVal })}
                      className="px-2 py-0.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium cursor-pointer"
                    >
                      {mVal.toLocaleString("en-IN")} m
                    </button>
                  ))
                : [
                    { u: 79, label: "79 kWh (Free)" },
                    { u: 1828, label: "1,828 kWh" },
                    { u: 4346, label: "4,346 kWh" },
                    { u: 6361, label: "6,361 kWh" },
                    { u: 8360, label: "8,360 kWh" },
                  ].map((q) => (
                    <button
                      key={q.u}
                      type="button"
                      onClick={() => void runEbCalc({ overrideUnits: q.u })}
                      className="px-2 py-0.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium cursor-pointer"
                    >
                      {q.label}
                    </button>
                  ))}
            </div>

            {calcResult && (
              <div className="grid md:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-1.5 pr-2">Slab</th>
                        <th className="py-1.5 pr-2">Unit Range</th>
                        <th className="py-1.5 pr-2">Units</th>
                        <th className="py-1.5 pr-2">Rate</th>
                        <th className="py-1.5 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {calcResult.slabs.map((s) => (
                        <tr key={s.slab_no}>
                          <td className="py-1.5 pr-2 font-semibold">Slab {s.slab_no}</td>
                          <td className="py-1.5 pr-2">
                            {s.from_unit} – {s.to_unit ?? "Above"}
                          </td>
                          <td className="py-1.5 pr-2">{s.units_in_slab.toLocaleString("en-IN")}</td>
                          <td className="py-1.5 pr-2">{formatRupeesFromPaise(s.rate_paise_per_unit)}/u</td>
                          <td className="py-1.5 text-right font-semibold">{formatRupeesFromPaise(s.amount_paise)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs content-start">
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <div className="text-slate-500">CC (Energy) Charge</div>
                    <div className="text-sm font-bold">{formatRupeesFromPaise(calcResult.energy_paise)}</div>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <div className="text-slate-500">Fixed Charge ({calcResult.sanctioned_kw} kW)</div>
                    <div className="text-sm font-bold">{formatRupeesFromPaise(calcResult.fixed_paise)}</div>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <div className="text-slate-500">Electricity Tax + FPPCA</div>
                    <div className="text-sm font-bold">
                      {formatRupeesFromPaise(calcResult.tax_paise + calcResult.fppca_paise)}
                    </div>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <div className="text-slate-500">Effective Rate / Unit</div>
                    <div className="text-sm font-bold">{formatRupeesFromPaise(calcResult.avg_paise_per_kwh)} / kWh</div>
                  </div>
                  <div
                    className={`col-span-2 p-3 rounded-lg border flex items-center justify-between ${
                      calcResult.free_quota_applied
                        ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                        : "bg-amber-50 border-amber-300 text-amber-950"
                    }`}
                  >
                    <div>
                      <div className="text-[11px] font-semibold">
                        {calcResult.free_quota_applied
                          ? "Free Quota Applied (≤ 1,000 units — Fixed & E-Tax Waived)"
                          : `Payable EB Bill (${calcResult.units_kwh.toLocaleString("en-IN")} kWh · ${calcResult.billing_days}d)`}
                      </div>
                      <div className="text-[11px] opacity-75">Exact: {formatRupeesFromPaise(calcResult.net_bill_paise)}</div>
                    </div>
                    <div className="text-xl font-extrabold">
                      ₹{calcResult.rounded_payable_rupees.toLocaleString("en-IN")}
                    </div>
                  </div>
                  {calcActiveMetres && calcActiveMetres > 0 && (
                    <div className="col-span-2 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-950 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                      <span>
                        <b>{calcActiveMetres.toLocaleString("en-IN")} m</b> woven ·{" "}
                        <b>{(calcResult.units_kwh / calcActiveMetres).toFixed(3)} kWh/m</b> ·{" "}
                        <b>
                          {calcResult.units_kwh > 0 ? (calcActiveMetres / calcResult.units_kwh).toFixed(2) : "0"} m/kWh
                        </b>
                      </span>
                      <span className="font-bold">
                        EB Cost: ₹{(calcResult.net_bill_paise / 100 / calcActiveMetres).toFixed(2)}/m (
                        {(
                          (calcResult.net_bill_paise /
                            100 /
                            Math.max(1, calcActiveMetres * (parseFloat(calcClothRateRs) || 6.0))) *
                          100
                        ).toFixed(1)}
                        % of ₹{parseFloat(calcClothRateRs) || 6}/m revenue)
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* EB Bill vs Metres Produced (Power Efficiency & Meter Health) */}
          {overview.eb_efficiency && (
            <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-bold flex items-center gap-1.5">
                    <Zap className="w-4 h-4 text-emerald-600" />
                    EB Bill vs. Metres Produced (Power Efficiency &amp; Meter Health)
                  </h2>
                  <p className="text-xs text-slate-500">
                    Matches each EB billing period against cloth woven (Daily Shifts or Deliveries) to track kWh/m, EB cost per metre, and catch faulty/under-reading meters.
                  </p>
                </div>
                <span className="px-2.5 py-1 rounded bg-slate-100 text-slate-700 text-[11px] font-semibold">
                  Baseline: {overview.eb_efficiency.baseline_kwh_per_metre} kWh/m
                </span>
              </div>

              <div className="grid sm:grid-cols-3 gap-2.5 text-xs">
                <div className="bg-slate-50 p-3 rounded-lg">
                  <div className="text-slate-500">Avg Power per Metre</div>
                  <div className="text-lg font-bold">
                    {overview.eb_efficiency.avg_kwh_per_metre !== null
                      ? `${overview.eb_efficiency.avg_kwh_per_metre} kWh/m`
                      : "Pending paired data"}
                  </div>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <div className="text-slate-500">Avg Cloth per Unit</div>
                  <div className="text-lg font-bold">
                    {overview.eb_efficiency.avg_metres_per_kwh !== null
                      ? `${overview.eb_efficiency.avg_metres_per_kwh} m/kWh`
                      : "Pending paired data"}
                  </div>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-lg">
                  <div className="text-emerald-900">Avg EB Cost per Metre</div>
                  <div className="text-lg font-bold text-emerald-900">
                    {overview.eb_efficiency.avg_eb_paise_per_metre !== null
                      ? `${formatRupeesFromPaise(overview.eb_efficiency.avg_eb_paise_per_metre)} / m`
                      : "Pending paired data"}
                  </div>
                </div>
              </div>

              {/* Period-by-period comparison table */}
              <div className="overflow-x-auto">
                {overview.eb_efficiency.periods.length === 0 ? (
                  <div className="text-xs text-slate-500 py-2">
                    No EB bills recorded yet. Add bi-monthly EB bills under Deliveries &amp; EB to compare against cloth produced.
                  </div>
                ) : (
                  <table className="w-full text-xs text-left">
                    <thead className="border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-1.5 pr-2">EB Billing Period</th>
                        <th className="py-1.5 pr-2">Metres Woven</th>
                        <th className="py-1.5 pr-2">EB Units</th>
                        <th className="py-1.5 pr-2">EB Bill</th>
                        <th className="py-1.5 pr-2">kWh / m</th>
                        <th className="py-1.5 pr-2">m / kWh</th>
                        <th className="py-1.5 pr-2">EB Cost / m</th>
                        <th className="py-1.5">Meter Health</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {overview.eb_efficiency.periods.map((p) => (
                        <tr key={p.bill_id}>
                          <td className="py-1.5 pr-2 font-medium whitespace-nowrap">
                            {formatDateDMY(p.period_start)} – {formatDateDMY(p.period_end)}{" "}
                            <span className="text-[10px] text-slate-400">({p.days}d)</span>
                          </td>
                          <td className="py-1.5 pr-2 font-semibold">
                            {p.metres_produced > 0 ? `${p.metres_produced.toLocaleString("en-IN")} m` : "-"}{" "}
                            {p.metres_source !== "NONE" && (
                              <span className="text-[10px] text-slate-400">
                                ({p.metres_source === "SHIFTS" ? "Shifts" : "Deliveries"})
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 pr-2">{p.units_kwh.toLocaleString("en-IN")} kWh</td>
                          <td className="py-1.5 pr-2 font-semibold">{formatRupeesFromPaise(p.net_bill_paise)}</td>
                          <td className="py-1.5 pr-2">{p.kwh_per_metre !== null ? p.kwh_per_metre.toFixed(3) : "-"}</td>
                          <td className="py-1.5 pr-2">{p.metres_per_kwh !== null ? p.metres_per_kwh.toFixed(2) : "-"}</td>
                          <td className="py-1.5 pr-2 font-semibold">
                            {p.eb_paise_per_metre !== null ? `${formatRupeesFromPaise(p.eb_paise_per_metre)}/m` : "-"}
                          </td>
                          <td className="py-1.5">
                            <span
                              title={p.status_note}
                              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                p.status_flag === "NORMAL"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : p.status_flag === "METER_UNDER_READING"
                                    ? "bg-rose-100 text-rose-800"
                                    : p.status_flag === "HIGH_POWER_USAGE"
                                      ? "bg-amber-100 text-amber-900"
                                      : "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {p.status_flag === "NORMAL"
                                ? "Normal"
                                : p.status_flag === "METER_UNDER_READING"
                                  ? "Meter Under-Reading"
                                  : p.status_flag === "HIGH_POWER_USAGE"
                                    ? "High Power Usage"
                                    : "No Metres"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Helpful cross-page shortcuts instead of duplicate estimator */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="text-slate-500">
                  Missing metres on a past EB bill? Log daily shifts or add/import your weekly delivery challans to auto-fill these rows.
                </span>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to="/today"
                    className="px-3 py-1.5 rounded-lg bg-slate-900 text-white font-semibold hover:bg-slate-800"
                  >
                    + Log Daily Shift →
                  </Link>
                  {isOwner && (
                    <Link
                      to="/deliveries"
                      className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 font-semibold hover:bg-slate-50"
                    >
                      Add Deliveries / EB Bills →
                    </Link>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Excel (.xlsx) & Printable Statement */}
      {tab === "reports" && isOwner && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3 no-print">
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-semibold text-slate-600">Statement Trader Filter:</label>
              <select
                value={stmtTraderId}
                onChange={(e) => setStmtTraderId(e.target.value)}
                className="px-3 py-1.5 rounded border border-slate-300 text-xs bg-white"
              >
                <option value="">All Traders (Full Shed 30-Day Statement)</option>
                {traders.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.company_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void downloadProtectedFile("/exports/xlsx/workbook", "loomos_full_report.xlsx")}
                className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
              >
                <FileSpreadsheet className="w-4 h-4" /> Download 7-Sheet Excel (.xlsx)
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Printer className="w-4 h-4" /> Print / Save PDF Statement
              </button>
            </div>
          </div>

          {statement && (
            <div className="printable-area bg-white p-5 rounded-xl border border-slate-200 space-y-4 text-xs">
              <div className="border-b border-slate-200 pb-3 flex justify-between items-start">
                <div>
                  <div className="text-base font-bold text-slate-900">{statement.unit_name} — Monthly Operations &amp; Account Statement</div>
                  <div className="text-slate-500">
                    Period: {formatDateDMY(statement.period_start)} to {formatDateDMY(statement.period_end)} · Cloth Woven:{" "}
                    <b>{statement.period_metres} m</b>
                  </div>
                </div>
                <div className="text-right font-bold text-emerald-700">
                  Net Operating: {formatRupeesFromPaise(statement.financials.net_operating_paise)}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="bg-slate-50 p-2.5 rounded">
                  Billed Revenue: <b>{formatRupeesFromPaise(statement.financials.billed_revenue_paise)}</b>
                </div>
                <div className="bg-slate-50 p-2.5 rounded">
                  Wages + EB + Exp:{" "}
                  <b>
                    {formatRupeesFromPaise(
                      statement.financials.finalized_wages_paise +
                        statement.financials.eb_bills_paise +
                        statement.financials.expenses_paise
                    )}
                  </b>
                </div>
                <div className="bg-slate-50 p-2.5 rounded">
                  All-Time Receivables: <b>{formatRupeesFromPaise(statement.financials.total_receivable_paise)}</b>
                </div>
                <div className="bg-slate-50 p-2.5 rounded">
                  Rate-Cut Shortfall: <b className="text-rose-700">{formatRupeesFromPaise(statement.financials.total_rate_underpayment_paise)}</b>
                </div>
              </div>

              <div>
                <h3 className="font-bold mb-1.5">Delivery Challans ({statement.deliveries.length})</h3>
                <table className="w-full text-left">
                  <thead className="border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="py-1 pr-2">Challan</th>
                      <th className="py-1 pr-2">Date</th>
                      <th className="py-1 pr-2">Trader</th>
                      <th className="py-1 pr-2">Metres</th>
                      <th className="py-1">Billed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {statement.deliveries.map((d) => (
                      <tr key={d.challan_no}>
                        <td className="py-1 pr-2 font-bold">{d.challan_no}</td>
                        <td className="py-1 pr-2">{formatDateDMY(d.delivery_date)}</td>
                        <td className="py-1 pr-2">{d.trader_name}</td>
                        <td className="py-1 pr-2">{d.total_metres} m</td>
                        <td className="py-1 font-semibold">{formatRupeesFromPaise(d.amount_paise)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Expansion Simulator (20/30/50/100 Looms) */}
      {tab === "simulator" && isOwner && simResult && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Calculator className="w-4 h-4 text-amber-600" />
                Shuttle Powerloom Expansion Simulator (P&amp;L, EMI, Payback &amp; Sensitivity)
              </h2>
              <div className="flex gap-1.5 text-xs font-bold">
                {[20, 30, 50, 100].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => void runCustomSimulation(n)}
                    className={`px-3 py-1 rounded-lg border cursor-pointer ${
                      simLooms === n ? "bg-amber-500 text-slate-950 border-amber-500" : "bg-white border-slate-300"
                    }`}
                  >
                    {n} Looms
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-7 gap-2.5 text-xs">
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Loom Count</label>
                <input type="number" min={1} max={500} value={simLooms} onChange={(e) => setSimLooms(Number(e.target.value))} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Shuttle RPM</label>
                <input type="number" min={60} max={2000} value={simRpm} onChange={(e) => setSimRpm(Number(e.target.value))} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Efficiency (%)</label>
                <input type="number" min={40} max={98} value={simEff} onChange={(e) => setSimEff(Number(e.target.value))} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Job Rate (₹/m)</label>
                <input type="number" step="0.1" min="1" value={simRate} onChange={(e) => setSimRate(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Machine Cost / Loom (₹)</label>
                <input type="number" step="1000" min="1000" value={simCapex} onChange={(e) => setSimCapex(e.target.value)} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Bank Loan (%)</label>
                <input type="number" min={0} max={95} value={simLoanPct} onChange={(e) => setSimLoanPct(Number(e.target.value))} className="w-full px-2.5 py-1.5 rounded border border-slate-300" />
              </div>
              <div className="flex items-end">
                <button type="button" onClick={() => void runCustomSimulation()} className="w-full py-1.5 px-3 rounded-lg bg-slate-900 text-white font-bold cursor-pointer">
                  Recalculate
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs pt-2">
              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-500">Monthly Income ({simResult.primary.loom_count} looms)</div>
                <div className="text-lg font-bold">{formatRupeesFromPaise(simResult.primary.gross_revenue_paise)}</div>
                <div className="text-[11px] text-slate-500">{simResult.primary.monthly_metres} m / month</div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-500">Monthly Profit (Before Loan)</div>
                <div className="text-lg font-bold text-emerald-700">{formatRupeesFromPaise(simResult.primary.ebitda_paise)}</div>
                <div className="text-[11px] text-slate-500">EB Bill: {formatRupeesFromPaise(simResult.primary.eb_monthly_paise)}/mo</div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg">
                <div className="text-slate-500">Cash Left After Loan EMI</div>
                <div className="text-lg font-bold">{formatRupeesFromPaise(simResult.primary.net_after_emi_paise)}</div>
                <div className="text-[11px] text-slate-500">Loan EMI: {formatRupeesFromPaise(simResult.primary.emi_paise)}/mo</div>
              </div>
              <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                <div className="text-amber-900">Months to Recover Cost</div>
                <div className="text-lg font-bold text-amber-900">
                  {simResult.primary.payback_months ? `${simResult.primary.payback_months} months` : "N/A"}
                </div>
                <div className="text-[11px] text-amber-800">Total Investment: {formatRupeesFromPaise(simResult.primary.total_capex_paise)}</div>
              </div>
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 overflow-x-auto space-y-2">
            <h3 className="text-sm font-bold">20 / 30 / 50 / 100 Loom Preset Comparison</h3>
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-1.5 pr-2">Looms</th>
                  <th className="py-1.5 pr-2">Metres/Mo</th>
                  <th className="py-1.5 pr-2">EB Bill/Mo</th>
                  <th className="py-1.5 pr-2">Monthly Profit</th>
                  <th className="py-1.5">Payback Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {simResult.presets.map((p) => (
                  <tr key={p.loom_count} className={p.loom_count === simResult.primary.loom_count ? "bg-amber-50/70 font-semibold" : ""}>
                    <td className="py-1.5 pr-2 font-bold">{p.loom_count}</td>
                    <td className="py-1.5 pr-2">{p.monthly_metres} m</td>
                    <td className="py-1.5 pr-2">{formatRupeesFromPaise(p.eb_monthly_paise)}</td>
                    <td className="py-1.5 pr-2 text-emerald-700 font-semibold">{formatRupeesFromPaise(p.ebitda_paise)}</td>
                    <td className="py-1.5">{p.payback_months ? `${p.payback_months} mo` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <TechnicalDetailsToggle
            title="Show 5×5 Rate × Efficiency Profit Sensitivity Matrix (Thesis Details)"
            subtitle="See how monthly profit changes if trader job rate or loom speed goes up or down"
          >
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-1.5 pr-2">Rate \ Efficiency</th>
                    {simResult.sensitivity_efficiencies.map((eff) => (
                      <th key={eff} className="py-1.5 pr-2">
                        {eff}%
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {simResult.sensitivity_matrix.map((row) => (
                    <tr key={row.rate_rs}>
                      <td className="py-1.5 pr-2 font-bold">₹{row.rate_rs.toFixed(2)}</td>
                      {row.cells.map((c) => (
                        <td
                          key={c.efficiency_pct}
                          className={`py-1.5 pr-2 ${c.ebitda_paise > 0 ? "text-emerald-700" : "text-rose-700 font-semibold"}`}
                        >
                          {formatRupeesFromPaise(c.ebitda_paise)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TechnicalDetailsToggle>
        </div>
      )}
    </div>
  );
}

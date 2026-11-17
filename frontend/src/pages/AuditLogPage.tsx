import { useEffect, useState } from "react";
import { apiRequest, formatDateDMY, formatDateTimeIST, formatHoursFromMins, formatRupeesFromPaise } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { AuditLogEntry } from "../types/api";

const FIELD_LABELS: Record<string, string> = {
  full_name: "Name",
  username: "Username",
  role: "Role",
  preferred_lang: "App Language",
  preferred_slip_lang: "Slip Language",
  is_active: "Status",
  loom_number: "Loom No",
  loom_type: "Type",
  rated_rpm: "Speed (RPM)",
  status: "Status",
  sort_name: "Fabric Sort",
  agreed_rate_paise: "Agreed Rate",
  expected_weft_kg_per_100m: "Expected Weft kg/100m",
  wastage_pct: "Allowed Wastage %",
  wage_mode: "Wage Mode",
  rate_paise: "Pay Rate",
  effective_from: "From Date",
  effective_to: "To Date",
  challan_no: "Challan No",
  delivery_date: "Delivery Date",
  total_metres: "Total Metres",
  amount_paise: "Amount",
  payment_date: "Payment Date",
  expense_date: "Expense Date",
  category: "Category",
  unit_name: "Shed Name",
  sanctioned_kw: "EB Load (kW)",
  shifts_per_day: "Shifts / Day",
  planned_shift_mins: "Shift Duration",
  net_metres: "Net Metres",
  downtime_mins: "Stopped Duration",
  entry_date: "Shift Date",
  shift_no: "Shift #",
  period_start: "Period Start",
  period_end: "Period End",
  net_bill_paise: "Net Bill",
  units_consumed: "Units (kWh)",
  billing_cycle_days: "Billing Cycle (Days)",
  overhead_per_kw_paise: "Overhead / kW",
  gross_paise: "Gross Pay",
  net_payable_paise: "Net Pay",
  is_working_day: "Working Day",
  planned_shifts: "Planned Shifts",
  note: "Note",
  weaver_id: "Worker ID",
  loom_id: "Loom ID",
  trader_id: "Trader ID",
  beam_id: "Beam ID",
  looms: "Looms",
  db: "Database",
};

function formatReadableAuditValues(rawJson: string | null): string[] {
  if (!rawJson) return [];
  try {
    const obj = JSON.parse(rawJson) as Record<string, unknown>;
    return Object.entries(obj)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => {
        const rawLabel = FIELD_LABELS[k] ?? k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        const label = k.endsWith("_paise") && !FIELD_LABELS[k] ? rawLabel.replace(/ Paise$/i, "") : rawLabel;
        if (k === "is_active") return `${label}: ${v ? "Active" : "Inactive"}`;
        if (typeof v === "boolean") return `${label}: ${v ? "Yes" : "No"}`;
        if (k.endsWith("_paise") && typeof v === "number") return `${label}: ${formatRupeesFromPaise(v)}`;
        if (k.endsWith("_mins") && typeof v === "number") return `${label}: ${formatHoursFromMins(v)} hrs`;
        if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) return `${label}: ${formatDateDMY(v)}`;
        return `${label}: ${String(v)}`;
      });
  } catch {
    return [rawJson];
  }
}

export function AuditLogPage() {
  const { t } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [entityFilter, setEntityFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const qs = entityFilter ? `?entity_type=${encodeURIComponent(entityFilter)}` : "";
        const data = await apiRequest<AuditLogEntry[]>(`/audit-logs${qs}`);
        setLogs(data);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [entityFilter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{t("auditTitle")}</h1>
          <p className="text-xs text-slate-500">
            Plain record of every change, rate edit, or removal — showing who changed what and why.
          </p>
        </div>
        <select
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm"
        >
          <option value="">All Records</option>
          <option value="fabric_sort">Fabric Sorts &amp; Rates</option>
          <option value="wage_rule">Wage Rules</option>
          <option value="weaver">Workers</option>
          <option value="shift_entry">Daily Shifts</option>
          <option value="delivery">Deliveries</option>
          <option value="trader_payment">Payments</option>
          <option value="expense">Expenses</option>
          <option value="eb_bill">EB Bills</option>
          <option value="loom">Looms</option>
          <option value="user">Users</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto shadow-sm">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-100 text-slate-700 font-semibold">
            <tr>
              <th className="px-3 py-2.5 text-left">When (IST)</th>
              <th className="px-3 py-2.5 text-left">Record</th>
              <th className="px-3 py-2.5 text-left">Action</th>
              <th className="px-3 py-2.5 text-left">Before</th>
              <th className="px-3 py-2.5 text-left">After</th>
              <th className="px-3 py-2.5 text-left">Reason / Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Loading change history...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No records yet.
                </td>
              </tr>
            ) : (
              logs.map((row) => {
                const oldItems = formatReadableAuditValues(row.old_values_json);
                const newItems = formatReadableAuditValues(row.new_values_json);
                const cleanEntity = row.entity_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                const cleanAction = row.action === "SOFT_DELETE" ? "REMOVED / VOIDED" : row.action;
                return (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                      {formatDateTimeIST(row.changed_at)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap font-semibold text-slate-800">
                      {cleanEntity} #{row.entity_id}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 rounded font-semibold ${
                          row.action === "SOFT_DELETE" || row.action === "DELETE"
                            ? "bg-rose-100 text-rose-800"
                            : row.action === "UPDATE" || row.action === "ARCHIVE"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {cleanAction}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {oldItems.length === 0 ? (
                        "—"
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {oldItems.map((item, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                              {item}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-800">
                      {newItems.length === 0 ? (
                        "—"
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {newItems.map((item, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-900">
                              {item}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-600">{row.reason ?? "—"}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

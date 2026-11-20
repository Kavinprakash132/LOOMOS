import React, { useState } from "react";
import { Plus, Trash2, Download, Upload, Factory, CheckCircle2 } from "lucide-react";
import { apiRequest } from "../api/client";
import { DemoBanner } from "../components/DemoBanner";
import { PasswordInput } from "../components/PasswordInput";
import { useAuth } from "../context/AuthContext";
import {
  AuthTokenResponse,
  EntryMode,
  HistoricalDeliverySeedRow,
  HistoricalEbSeedRow,
  LangCode,
  LoomGroupInput,
} from "../types/api";

function parseCsvRows(text: string): string[][] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split(",").map((cell) => cell.trim()));
}

export function SetupPage() {
  const { lang, t, toggleLanguage, completeAuth } = useAuth();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Step 1: Owner & Unit Identity (first!)
  const [ownerFullName, setOwnerFullName] = useState("");
  const [ownerUsername, setOwnerUsername] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [unitName, setUnitName] = useState("");
  const [location, setLocation] = useState("");
  const [defaultLang, setDefaultLang] = useState<LangCode>(lang);

  // Step 2: Dynamic N-Loom Sizing
  const [shiftsPerDay, setShiftsPerDay] = useState(2);
  const [defaultEntryMode, setDefaultEntryMode] = useState<EntryMode>("DIRECT");
  const [loomGroups, setLoomGroups] = useState<LoomGroupInput[]>([
    {
      count: 5,
      prefix: "S-",
      start_number: 1,
      loom_type: "SHUTTLE",
      make_model: "",
      rated_rpm: 160,
      reed_space_in: 56,
    },
  ]);

  // Step 3: Clean / CSV History / Labelled Demo
  const [seedMode, setSeedMode] = useState<"CLEAN" | "CSV_IMPORT" | "SAMPLE_DEMO">("CLEAN");
  const [ebCsvRows, setEbCsvRows] = useState<HistoricalEbSeedRow[]>([]);
  const [delCsvRows, setDelCsvRows] = useState<HistoricalDeliverySeedRow[]>([]);
  const [csvSummary, setCsvSummary] = useState<string>("");

  const [attemptedStep1, setAttemptedStep1] = useState(false);
  const [attemptedStep2, setAttemptedStep2] = useState(false);

  const totalLooms = loomGroups.reduce((acc, g) => acc + (Number(g.count) || 0), 0);
  const ownerNameInvalid = attemptedStep1 && ownerFullName.trim().length < 2;
  const ownerUserInvalid = attemptedStep1 && ownerUsername.trim().length < 3;
  const ownerPassInvalid = attemptedStep1 && ownerPassword.length < 6;
  const unitNameInvalid = attemptedStep1 && unitName.trim().length < 2;

  const handleEbFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const rows = parseCsvRows(await file.text());
    const parsed: HistoricalEbSeedRow[] = [];
    for (const cols of rows.slice(1)) {
      if (cols.length < 4 || !cols[0]) continue;
      const billNum = parseFloat(cols[3]);
      if (!Number.isFinite(billNum) || billNum < 0) continue;
      parsed.push({
        period_start: cols[0],
        period_end: cols[1],
        units_consumed: cols[2],
        net_bill_paise: Math.round(billNum * 100),
        total_power_cut_mins: cols[4] ? parseInt(cols[4], 10) || 0 : 0,
        notes: cols[5] ?? undefined,
      });
    }
    setEbCsvRows(parsed);
    setCsvSummary(`Loaded ${parsed.length} EB bills, ${delCsvRows.length} deliveries`);
  };

  const handleDelFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const rows = parseCsvRows(await file.text());
    const parsed: HistoricalDeliverySeedRow[] = [];
    for (const cols of rows.slice(1)) {
      if (cols.length < 6 || !cols[0]) continue;
      const rateNum = parseFloat(cols[5]);
      if (!Number.isFinite(rateNum) || rateNum <= 0) continue;
      parsed.push({
        delivery_date: cols[0],
        trader_name: cols[1],
        challan_no: cols[2],
        sort_name: cols[3] || undefined,
        metres: cols[4],
        applied_rate_paise: Math.round(rateNum * 100),
      });
    }
    setDelCsvRows(parsed);
    setCsvSummary(`Loaded ${ebCsvRows.length} EB bills, ${parsed.length} deliveries`);
  };

  const handleNextStep1 = (e: React.FormEvent) => {
    e.preventDefault();
    setAttemptedStep1(true);
    setError(null);
    if (
      ownerFullName.trim().length < 2 ||
      ownerUsername.trim().length < 3 ||
      ownerPassword.length < 6 ||
      unitName.trim().length < 2
    ) {
      setError(t("fillRequiredFields"));
      return;
    }
    setStep(2);
  };

  const handleNextStep2 = () => {
    setAttemptedStep2(true);
    setError(null);
    const badGroup = loomGroups.find(
      (g) => !g.prefix.trim() || Number(g.count) < 1 || Number(g.rated_rpm) < 40
    );
    if (badGroup || totalLooms < 1) {
      setError("Enter valid loom count (1+), prefix, and RPM (40+) for all highlighted groups.");
      return;
    }
    setStep(3);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (totalLooms < 1) {
      setError("Add at least 1 loom.");
      return;
    }
    setSubmitting(true);
    try {
      const resp = await apiRequest<AuthTokenResponse>("/setup/initialize", {
        method: "POST",
        body: JSON.stringify({
          owner_full_name: ownerFullName,
          owner_username: ownerUsername,
          owner_password: ownerPassword,
          unit_name: unitName,
          location,
          default_language: defaultLang,
          loom_groups: loomGroups,
          shifts_per_day: shiftsPerDay,
          default_entry_mode: defaultEntryMode,
          seed_mode: seedMode,
          historical_eb_bills: seedMode === "CSV_IMPORT" ? ebCsvRows : [],
          historical_deliveries: seedMode === "CSV_IMPORT" ? delCsvRows : [],
        }),
      });
      completeAuth(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      <DemoBanner />
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
        <div className="bg-slate-900 text-white px-6 py-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Factory className="w-7 h-7 text-amber-400 shrink-0" />
            <div>
              <h1 className="text-lg font-bold">{t("setupHeader")}</h1>
              <p className="text-xs text-slate-300">{t("setupSub")}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              const next: LangCode = lang === "en" ? "ta" : "en";
              setDefaultLang(next);
              void toggleLanguage(next);
            }}
            className="px-3 py-1.5 rounded border border-slate-700 text-xs font-semibold shrink-0 hover:bg-slate-800"
          >
            {lang === "en" ? "EN | தமிழ்" : "தமிழ் | EN"}
          </button>
        </div>

        {/* Step Indicator */}
        <div className="grid grid-cols-3 text-xs font-semibold border-b border-slate-200 bg-slate-50">
          {[
            { num: 1, label: t("step1Title") },
            { num: 2, label: t("step2Title") },
            { num: 3, label: t("step3Title") },
          ].map((s) => (
            <div
              key={s.num}
              className={`px-3 py-2.5 text-center border-b-2 ${
                step === s.num
                  ? "border-amber-500 text-amber-700 bg-white"
                  : step > s.num
                  ? "border-emerald-500 text-emerald-700"
                  : "border-transparent text-slate-400"
              }`}
            >
              {s.label}
            </div>
          ))}
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
              {error}
            </div>
          )}

          {step === 1 && (
            <form noValidate onSubmit={handleNextStep1} className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    {t("ownerName")} <span className="text-rose-600">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    value={ownerFullName}
                    onChange={(e) => setOwnerFullName(e.target.value)}
                    placeholder="e.g. Ramasamy K"
                    className={`w-full px-3 py-2 rounded-lg border text-sm ${
                      ownerNameInvalid ? "field-invalid" : "border-slate-300"
                    }`}
                  />
                  {ownerNameInvalid && (
                    <p className="mt-1 text-xs text-rose-600 font-medium">{t("min2Chars")}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    {t("username")} <span className="text-rose-600">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    minLength={3}
                    value={ownerUsername}
                    onChange={(e) => setOwnerUsername(e.target.value)}
                    placeholder="e.g. owner_ram"
                    className={`w-full px-3 py-2 rounded-lg border text-sm ${
                      ownerUserInvalid ? "field-invalid" : "border-slate-300"
                    }`}
                  />
                  {ownerUserInvalid && (
                    <p className="mt-1 text-xs text-rose-600 font-medium">{t("min3Chars")}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  {t("password")} <span className="text-rose-600">*</span>
                </label>
                <PasswordInput
                  required
                  minLength={6}
                  autoComplete="new-password"
                  showLabel={t("showPassword")}
                  hideLabel={t("hidePassword")}
                  value={ownerPassword}
                  onChange={(e) => setOwnerPassword(e.target.value)}
                  className={`w-full px-3 py-2 rounded-lg border text-sm ${
                    ownerPassInvalid ? "field-invalid" : "border-slate-300"
                  }`}
                />
                {ownerPassInvalid && (
                  <p className="mt-1 text-xs text-rose-600 font-medium">{t("min6Chars")}</p>
                )}
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    {t("unitName")} <span className="text-rose-600">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    value={unitName}
                    onChange={(e) => setUnitName(e.target.value)}
                    placeholder="e.g. LOOMOS"
                    className={`w-full px-3 py-2 rounded-lg border text-sm ${
                      unitNameInvalid ? "field-invalid" : "border-slate-300"
                    }`}
                  />
                  {unitNameInvalid && (
                    <p className="mt-1 text-xs text-rose-600 font-medium">{t("shedNameRequired")}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    {t("location")}
                  </label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Palladam, Tiruppur"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold"
                >
                  {t("next")} →
                </button>
              </div>
            </form>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="space-y-3">
                {loomGroups.map((g, idx) => (
                  <div key={idx} className="p-3 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700">
                        Loom Group #{idx + 1} ({g.prefix}
                        {String(g.start_number).padStart(2, "0")} .. {g.prefix}
                        {String(g.start_number + Math.max(0, g.count - 1)).padStart(2, "0")})
                      </span>
                      {loomGroups.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setLoomGroups((prev) => prev.filter((_, i) => i !== idx))}
                          className="text-rose-600 hover:text-rose-800 p-1"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                          {t("loomCount")}
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={500}
                          value={g.count || ""}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10) || 0;
                            setLoomGroups((prev) =>
                              prev.map((row, i) => (i === idx ? { ...row, count: val } : row))
                            );
                          }}
                          className={`w-full px-2.5 py-1.5 rounded border bg-white text-sm ${
                            attemptedStep2 && g.count < 1 ? "field-invalid" : "border-slate-300"
                          }`}
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                          {t("loomPrefix")}
                        </label>
                        <input
                          type="text"
                          value={g.prefix}
                          onChange={(e) =>
                            setLoomGroups((prev) =>
                              prev.map((row, i) => (i === idx ? { ...row, prefix: e.target.value } : row))
                            )
                          }
                          className={`w-full px-2.5 py-1.5 rounded border bg-white text-sm ${
                            attemptedStep2 && !g.prefix.trim() ? "field-invalid" : "border-slate-300"
                          }`}
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                          {t("loomType")}
                        </label>
                        <div className="w-full px-2.5 py-1.5 rounded border border-slate-200 bg-slate-100 text-xs font-semibold text-slate-700">
                          Shuttle Powerloom
                        </div>
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                          {t("rpm")}
                        </label>
                        <input
                          type="number"
                          min={40}
                          max={2500}
                          value={g.rated_rpm || ""}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10) || 0;
                            setLoomGroups((prev) =>
                              prev.map((row, i) => (i === idx ? { ...row, rated_rpm: val } : row))
                            );
                          }}
                          className={`w-full px-2.5 py-1.5 rounded border bg-white text-sm ${
                            attemptedStep2 && g.rated_rpm < 40 ? "field-invalid" : "border-slate-300"
                          }`}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={() =>
                  setLoomGroups((prev) => [
                    ...prev,
                    {
                      count: 5,
                      prefix: "S-",
                      start_number: prev.reduce((s, r) => s + r.count, 1),
                      loom_type: "SHUTTLE",
                      make_model: "",
                      rated_rpm: 165,
                      reed_space_in: 56,
                    },
                  ])
                }
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700 hover:text-amber-800"
              >
                <Plus className="w-4 h-4" />
                Add Another Shuttle Loom Group (Different RPM / Prefix)
              </button>

              <div className="grid sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Shifts per Day</label>
                  <select
                    value={shiftsPerDay}
                    onChange={(e) => setShiftsPerDay(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  >
                    <option value={1}>1 Shift / Day</option>
                    <option value={2}>2 Shifts / Day (Day / Night)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Default Production Input
                  </label>
                  <select
                    value={defaultEntryMode}
                    onChange={(e) => setDefaultEntryMode(e.target.value as EntryMode)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  >
                    <option value="DIRECT">Direct Metres (e.g. 28.5 m)</option>
                    <option value="COUNTER">Meter Counter (End - Start)</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium"
                >
                  ← {t("back")}
                </button>
                <button
                  type="button"
                  onClick={handleNextStep2}
                  className="px-5 py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold"
                >
                  {t("next")} ({totalLooms} looms) →
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2.5">
                {[
                  {
                    id: "CLEAN" as const,
                    title: t("seedClean"),
                    desc: "Creates only your looms, editable TANGEDCO LA3A2 tariff preset, and standard stop reasons (incl. Power Cut).",
                  },
                  {
                    id: "CSV_IMPORT" as const,
                    title: t("seedCsv"),
                    desc: "Backfill your past weekly delivery records and EB bills right away so forecasts start with real history.",
                  },
                  {
                    id: "SAMPLE_DEMO" as const,
                    title: t("seedDemo"),
                    desc: "Adds clearly marked [DEMO] trader, sort, weaver/helper wage rules, and one sample EB bill for testing.",
                  },
                ].map((opt) => (
                  <label
                    key={opt.id}
                    className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition ${
                      seedMode === opt.id
                        ? "border-amber-500 bg-amber-50/60"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="radio"
                      name="seedMode"
                      checked={seedMode === opt.id}
                      onChange={() => setSeedMode(opt.id)}
                      className="mt-1"
                    />
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{opt.title}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{opt.desc}</div>
                    </div>
                  </label>
                ))}
              </div>

              {seedMode === "CSV_IMPORT" && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <a
                      href="/api/v1/setup/templates/eb_bills"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-white border border-slate-300 text-xs font-medium hover:bg-slate-100"
                    >
                      <Download className="w-3.5 h-3.5" /> {t("dlEbTpl")}
                    </a>
                    <a
                      href="/api/v1/setup/templates/deliveries"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-white border border-slate-300 text-xs font-medium hover:bg-slate-100"
                    >
                      <Download className="w-3.5 h-3.5" /> {t("dlDelTpl")}
                    </a>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-3 text-xs">
                    <label className="block p-3 rounded-lg border border-dashed border-slate-300 bg-white cursor-pointer">
                      <span className="flex items-center gap-1.5 font-semibold text-slate-700 mb-1">
                        <Upload className="w-3.5 h-3.5" /> EB Bills CSV
                      </span>
                      <input type="file" accept=".csv" onChange={handleEbFile} className="w-full" />
                    </label>
                    <label className="block p-3 rounded-lg border border-dashed border-slate-300 bg-white cursor-pointer">
                      <span className="flex items-center gap-1.5 font-semibold text-slate-700 mb-1">
                        <Upload className="w-3.5 h-3.5" /> Deliveries CSV
                      </span>
                      <input type="file" accept=".csv" onChange={handleDelFile} className="w-full" />
                    </label>
                  </div>
                  {csvSummary && <p className="text-xs font-medium text-emerald-700">{csvSummary}</p>}
                </div>
              )}

              <div className="flex justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-medium"
                >
                  ← {t("back")}
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-sm font-bold disabled:opacity-60"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  {submitting ? "Setting up..." : t("finishSetup")}
                </button>
              </div>
            </form>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}

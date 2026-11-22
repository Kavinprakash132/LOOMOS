import React, { useState } from "react";
import { Plus, X } from "lucide-react";
import { apiRequest, formatRupeesFromPaise } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { FabricSort, Trader } from "../../types/api";

export function TradersSortsTab({
  traders,
  sorts,
  onRefresh,
  onError,
}: {
  traders: Trader[];
  sorts: FabricSort[];
  onRefresh: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const { tr } = useAuth();
  const toast = useToast();
  const [showAddTrader, setShowAddTrader] = useState(false);
  const [showAddSort, setShowAddSort] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");

  const [sortName, setSortName] = useState("");
  const [reed, setReed] = useState(84);
  const [pick, setPick] = useState(76);
  const [widthIn, setWidthIn] = useState("48.00");
  const [rateRs, setRateRs] = useState("6.00");
  const [weftKgPer100m, setWeftKgPer100m] = useState("6.800");
  const [wastagePct, setWastagePct] = useState("2.50");

  const [editingSortId, setEditingSortId] = useState<number | null>(null);
  const [editRateDraft, setEditRateDraft] = useState("");

  const addTrader = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/traders", {
        method: "POST",
        body: JSON.stringify({ company_name: companyName, contact_name: contactName, phone }),
      });
      const addedCompany = companyName.trim();
      setCompanyName("");
      setContactName("");
      setPhone("");
      setShowAddTrader(false);
      toast.success(tr(`Trader ${addedCompany} added.`, `வியாபாரி ${addedCompany} சேர்க்கப்பட்டார்.`));
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add trader");
    }
  };

  const addSort = async (e: React.FormEvent) => {
    e.preventDefault();
    const ratePaise = Math.round(parseFloat(rateRs) * 100);
    if (!Number.isFinite(ratePaise) || ratePaise <= 0) {
      onError(tr("Enter a valid positive rate (₹/m).", "சரியான மீட்டர் விகிதத்தை உள்ளிடவும் (₹/மீ)."));
      return;
    }
    try {
      await apiRequest("/fabric-sorts", {
        method: "POST",
        body: JSON.stringify({
          sort_name: sortName,
          reed,
          pick,
          width_in: widthIn,
          agreed_rate_paise: ratePaise,
          expected_weft_kg_per_100m: weftKgPer100m,
          wastage_pct: wastagePct,
        }),
      });
      const addedSort = sortName.trim();
      setSortName("");
      setShowAddSort(false);
      toast.success(tr(`Fabric sort ${addedSort} added.`, `துணி வகை ${addedSort} சேர்க்கப்பட்டது.`));
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add sort");
    }
  };

  const saveEditedSortRate = async (sortId: number) => {
    const nextPaise = Math.round(parseFloat(editRateDraft) * 100);
    if (!Number.isFinite(nextPaise) || nextPaise <= 0) {
      onError("Enter a valid positive rate (₹/m).");
      return;
    }
    try {
      await apiRequest(`/fabric-sorts/${sortId}`, {
        method: "PATCH",
        body: JSON.stringify({ agreed_rate_paise: nextPaise }),
      });
      setEditingSortId(null);
      toast.success(tr("Agreed sort rate updated.", "துணி ஒப்பந்த விலை புதுப்பிக்கப்பட்டது."));
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Rate update failed");
    }
  };

  return (
    <div className="space-y-6">
      {/* Traders */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-slate-900">
            {tr(`Job-Work Traders (${traders.length})`, `வியாபாரிகள் (${traders.length})`)}
          </h3>
          <button
            type="button"
            onClick={() => setShowAddTrader((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
              showAddTrader ? "bg-slate-200 text-slate-800" : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            {showAddTrader ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {showAddTrader ? tr("Close", "மூடு") : tr("Add Trader", "வியாபாரி சேர்")}
          </button>
        </div>

        {showAddTrader && (
        <form onSubmit={addTrader} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Trader / Company Name", "வியாபாரி / நிறுவனப் பெயர்")} <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. Murugan Textiles"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Contact Person (optional)", "தொடர்பாளர் (விருப்பம்)")}</label>
              <input
                placeholder="e.g. Kumar"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Phone Number (optional)", "தொலைபேசி (விருப்பம்)")}</label>
              <input
                placeholder="e.g. 9876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold cursor-pointer">
            {tr("Save Trader", "வியாபாரி சேமி")}
          </button>
        </form>
        )}
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {traders.map((item) => (
            <div key={item.id} className="px-4 py-2.5 flex justify-between text-sm">
              <div>
                <span className="font-semibold">{item.company_name}</span>
                {item.contact_name && <span className="ml-2 text-xs text-slate-500">({item.contact_name})</span>}
              </div>
              <span className="text-xs text-slate-500">{item.phone || "—"}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Fabric Sorts */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-slate-900">
            {tr(`Fabric Sorts (${sorts.length})`, `துணி வகைகள் (${sorts.length})`)}
          </h3>
          <button
            type="button"
            onClick={() => setShowAddSort((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
              showAddSort ? "bg-slate-200 text-slate-800" : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            {showAddSort ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {showAddSort ? tr("Close", "மூடு") : tr("Add Fabric Sort", "துணி வகை சேர்")}
          </button>
        </div>

        {showAddSort && (
        <form onSubmit={addSort} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
          <div className="grid sm:grid-cols-4 gap-2">
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Fabric Sort Name", "துணி வகைப் பெயர்")} <span className="text-rose-600">*</span>
              </label>
              <input
                required
                placeholder="e.g. 40s x 40s Grey Gada"
                value={sortName}
                onChange={(e) => setSortName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Reed", "ரீட்")} <span className="text-rose-600">*</span>
              </label>
              <input
                type="number"
                required
                min={1}
                value={reed}
                onChange={(e) => setReed(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                {tr("Pick (PPI)", "பிக் (PPI)")} <span className="text-rose-600">*</span>
              </label>
              <input
                type="number"
                required
                min={1}
                value={pick}
                onChange={(e) => setPick(Number(e.target.value))}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <div className="grid sm:grid-cols-4 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Cloth Width (inches)", "துணி அகலம் (இன்ச்)")}</label>
              <input
                type="number"
                step="0.01"
                min="1"
                value={widthIn}
                onChange={(e) => setWidthIn(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Agreed Rate (₹/metre)", "ஒப்பந்த விலை (₹/மீ)")}</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={rateRs}
                onChange={(e) => setRateRs(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Expected Weft kg / 100m", "ஊடை எடை (கிலோ/100மீ)")}</label>
              <input
                type="number"
                step="0.001"
                min="0"
                value={weftKgPer100m}
                onChange={(e) => setWeftKgPer100m(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">{tr("Allowed Wastage (%)", "அனுமதி வீண் (%)")}</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="50"
                value={wastagePct}
                onChange={(e) => setWastagePct(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold cursor-pointer">
            {tr("Save Fabric Sort", "துணி வகை சேமி")}
          </button>
        </form>
        )}

        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-100 text-slate-700 font-semibold">
              <tr>
                <th className="px-3 py-2 text-left">{tr("Sort", "துணி வகை")}</th>
                <th className="px-3 py-2 text-left">{tr("Reed × Pick", "ரீட் × பிக்")}</th>
                <th className="px-3 py-2 text-left">{tr("Agreed Rate", "ஒப்பந்த விலை")}</th>
                <th className="px-3 py-2 text-left">{tr("Weft kg/100m", "ஊடை/100மீ")}</th>
                <th className="px-3 py-2 text-left">{tr("Wastage %", "வீண் %")}</th>
                <th className="px-3 py-2 text-left">{tr("Action", "செயல்")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sorts.map((s) => (
                <tr key={s.id}>
                  <td className="px-3 py-2 font-semibold">{s.sort_name}</td>
                  <td className="px-3 py-2">{s.reed} × {s.pick} ({s.width_in}")</td>
                  <td className="px-3 py-2 font-semibold text-emerald-700">
                    {editingSortId === s.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          value={editRateDraft}
                          onChange={(e) => setEditRateDraft(e.target.value)}
                          className="w-20 px-1.5 py-0.5 rounded border border-slate-300 text-xs text-slate-900"
                        />
                        <button
                          type="button"
                          onClick={() => void saveEditedSortRate(s.id)}
                          className="px-2 py-0.5 rounded bg-slate-900 text-white text-[11px]"
                        >
                          {tr("Save", "சேமி")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingSortId(null)}
                          className="text-slate-500 text-[11px]"
                        >
                          {tr("Cancel", "ரத்து")}
                        </button>
                      </div>
                    ) : (
                      `${formatRupeesFromPaise(s.agreed_rate_paise)}/m`
                    )}
                  </td>
                  <td className="px-3 py-2">{s.expected_weft_kg_per_100m} kg</td>
                  <td className="px-3 py-2">{s.wastage_pct}%</td>
                  <td className="px-3 py-2">
                    {editingSortId !== s.id && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditingSortId(s.id);
                          setEditRateDraft((s.agreed_rate_paise / 100).toFixed(2));
                        }}
                        className="text-amber-700 font-semibold hover:underline cursor-pointer"
                      >
                        {tr("Edit Rate", "விலை மாற்று")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

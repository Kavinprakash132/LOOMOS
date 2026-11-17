import React, { useState } from "react";
import { apiRequest, formatRupeesFromPaise } from "../../api/client";
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
      setCompanyName("");
      setContactName("");
      setPhone("");
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add trader");
    }
  };

  const addSort = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest("/fabric-sorts", {
        method: "POST",
        body: JSON.stringify({
          sort_name: sortName,
          reed,
          pick,
          width_in: widthIn,
          agreed_rate_paise: Math.round(parseFloat(rateRs) * 100),
          expected_weft_kg_per_100m: weftKgPer100m,
          wastage_pct: wastagePct,
        }),
      });
      setSortName("");
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
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Rate update failed");
    }
  };

  return (
    <div className="space-y-6">
      {/* Traders */}
      <div className="space-y-3">
        <form onSubmit={addTrader} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">Job-Work Traders (Parties Who Give Beams &amp; Pay Per Metre)</h3>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Trader / Company Name <span className="text-rose-600">*</span>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Contact Person (optional)</label>
              <input
                placeholder="e.g. Kumar"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Phone Number (optional)</label>
              <input
                placeholder="e.g. 9876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-300 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
            Add Trader
          </button>
        </form>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {traders.map((tr) => (
            <div key={tr.id} className="px-4 py-2.5 flex justify-between text-sm">
              <div>
                <span className="font-semibold">{tr.company_name}</span>
                {tr.contact_name && <span className="ml-2 text-xs text-slate-500">({tr.contact_name})</span>}
              </div>
              <span className="text-xs text-slate-500">{tr.phone || "—"}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Fabric Sorts */}
      <div className="space-y-3">
        <form onSubmit={addSort} className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h3 className="text-sm font-bold">Fabric Sorts (Used for Rate Checker, Speed Target &amp; Weft Wastage)</h3>
          <div className="grid sm:grid-cols-4 gap-2">
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Fabric Sort Name <span className="text-rose-600">*</span>
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
                Reed <span className="text-rose-600">*</span>
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
                Pick (PPI) <span className="text-rose-600">*</span>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Cloth Width (inches)</label>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Agreed Rate (₹/metre)</label>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Expected Weft kg / 100m</label>
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
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Allowed Wastage (%)</label>
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
          <button type="submit" className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold">
            Add Fabric Sort
          </button>
        </form>

        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-100 text-slate-700 font-semibold">
              <tr>
                <th className="px-3 py-2 text-left">Sort</th>
                <th className="px-3 py-2 text-left">Reed × Pick</th>
                <th className="px-3 py-2 text-left">Agreed Rate</th>
                <th className="px-3 py-2 text-left">Weft kg/100m</th>
                <th className="px-3 py-2 text-left">Wastage %</th>
                <th className="px-3 py-2 text-left">Action</th>
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
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingSortId(null)}
                          className="text-slate-500 text-[11px]"
                        >
                          Cancel
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
                        Edit Rate
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

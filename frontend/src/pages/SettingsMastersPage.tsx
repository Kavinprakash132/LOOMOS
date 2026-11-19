import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../api/client";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { EbAndStopsTab } from "../components/masters/EbAndStopsTab";
import { LoomsTab } from "../components/masters/LoomsTab";
import { TeamUnitTab } from "../components/masters/TeamUnitTab";
import { TradersSortsTab } from "../components/masters/TradersSortsTab";
import { WeaversTab } from "../components/masters/WeaversTab";
import { useAuth } from "../context/AuthContext";
import {
  EbTariffPlan,
  FabricSort,
  Loom,
  StopReason,
  Trader,
  UnitSettings,
  User,
  Weaver,
} from "../types/api";

type TabId = "looms" | "weavers" | "traders_sorts" | "eb_stops" | "team";

export function SettingsMastersPage() {
  const { t, refreshState } = useAuth();
  const [tab, setTab] = useState<TabId>("looms");
  const [error, setError] = useState<string | null>(null);
  const [looms, setLooms] = useState<Loom[]>([]);
  const [weavers, setWeavers] = useState<Weaver[]>([]);
  const [traders, setTraders] = useState<Trader[]>([]);
  const [sorts, setSorts] = useState<FabricSort[]>([]);
  const [plans, setPlans] = useState<EbTariffPlan[]>([]);
  const [stops, setStops] = useState<StopReason[]>([]);
  const [settings, setSettings] = useState<UnitSettings | null>(null);
  const [users, setUsers] = useState<User[]>([]);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [l, w, tr, sr, pl, st, se, us] = await Promise.all([
        apiRequest<Loom[]>("/looms?active_only=false"),
        apiRequest<Weaver[]>("/weavers?active_only=false"),
        apiRequest<Trader[]>("/traders?active_only=false"),
        apiRequest<FabricSort[]>("/fabric-sorts?active_only=false"),
        apiRequest<EbTariffPlan[]>("/eb-tariffs"),
        apiRequest<StopReason[]>("/stop-reasons?active_only=false"),
        apiRequest<UnitSettings>("/settings"),
        apiRequest<User[]>("/auth/users"),
      ]);
      setLooms(l);
      setWeavers(w);
      setTraders(tr);
      setSorts(sr);
      setPlans(pl);
      setStops(st);
      setSettings(se);
      setUsers(us);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load masters");
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleRefresh = async () => {
    await loadAll();
    await refreshState();
  };

  const activeLoomsCount = looms.filter((l) => l.is_active).length;

  const tabs: { id: TabId; label: string }[] = [
    { id: "looms", label: `${t("tabLooms")} (${activeLoomsCount})` },
    { id: "weavers", label: `${t("tabWeavers")} (${weavers.length})` },
    { id: "traders_sorts", label: `${t("tabTraders")} & ${t("tabSorts")}` },
    { id: "eb_stops", label: `${t("tabEb")} & ${t("tabStops")}` },
    { id: "team", label: t("tabTeam") },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">Shed Setup &amp; Masters</h1>

      <PageGuideBanner
        tip="Set up your shuttle looms, workers & wage rates, traders & cloth sorts, TNPDCL electricity slabs, and CSV historical imports here."
      />

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
              tab === item.id
                ? "bg-slate-900 text-white"
                : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "looms" && <LoomsTab looms={looms} onRefresh={handleRefresh} onError={setError} />}
      {tab === "weavers" && <WeaversTab weavers={weavers} onRefresh={handleRefresh} onError={setError} />}
      {tab === "traders_sorts" && (
        <TradersSortsTab traders={traders} sorts={sorts} onRefresh={handleRefresh} onError={setError} />
      )}
      {tab === "eb_stops" && (
        <EbAndStopsTab plans={plans} stops={stops} settings={settings} onRefresh={handleRefresh} onError={setError} />
      )}
      {tab === "team" && (
        <TeamUnitTab settings={settings} users={users} onRefresh={handleRefresh} onError={setError} />
      )}
    </div>
  );
}

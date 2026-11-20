import React, { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  Calculator,
  Camera,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Factory,
  FileSpreadsheet,
  History,
  Layers,
  LogOut,
  Settings,
  Sparkles,
  TrendingUp,
  Truck,
  Wallet,
  Zap,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { DemoBanner } from "./DemoBanner";

interface SubNavItem {
  to: string;
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  ownerOnly?: boolean;
  matchPath: string;
  matchTab?: string;
}

interface MainSection {
  id: "daily" | "money" | "tools";
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  ownerOnly?: boolean;
  items: SubNavItem[];
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, setupStatus, lang, t, toggleLanguage, logout } = useAuth();
  const location = useLocation();
  const isOwner = user?.role === "OWNER";

  const sections: MainSection[] = useMemo(() => {
    const raw: MainSection[] = [
      {
        id: "daily",
        title: t("secDaily"),
        icon: Factory,
        items: [
          { to: "/dashboard", label: t("navHome"), shortLabel: t("navHomeShort"), icon: BarChart3, matchPath: "/dashboard" },
          { to: "/today", label: t("navToday"), shortLabel: t("navTodayShort"), icon: ClipboardCheck, matchPath: "/today" },
          { to: "/beams", label: t("navBeams"), shortLabel: t("navBeamsShort"), icon: Layers, matchPath: "/beams" },
          { to: "/inspect", label: t("navInspect"), shortLabel: t("navInspectShort"), icon: Camera, matchPath: "/inspect" },
        ],
      },
      {
        id: "money",
        title: t("secMoney"),
        icon: Wallet,
        ownerOnly: true,
        items: [
          { to: "/payroll", label: t("navPayroll"), shortLabel: t("navPayrollShort"), icon: Wallet, ownerOnly: true, matchPath: "/payroll" },
          { to: "/deliveries", label: t("navDeliveries"), shortLabel: t("navDeliveriesShort"), icon: Truck, ownerOnly: true, matchPath: "/deliveries" },
          {
            to: "/analytics?tab=reports",
            label: t("navReports"),
            shortLabel: t("navReportsShort"),
            icon: FileSpreadsheet,
            ownerOnly: true,
            matchPath: "/analytics",
            matchTab: "reports",
          },
        ],
      },
      {
        id: "tools",
        title: t("secTools"),
        icon: Sparkles,
        items: [
          {
            to: "/analytics?tab=eb",
            label: t("navEbCalc"),
            shortLabel: t("navEbCalcShort"),
            icon: Zap,
            matchPath: "/analytics",
            matchTab: "eb",
          },
          {
            to: "/analytics?tab=forecast",
            label: t("navForecast"),
            shortLabel: t("navForecastShort"),
            icon: TrendingUp,
            matchPath: "/analytics",
            matchTab: "forecast",
          },
          {
            to: "/analytics?tab=simulator",
            label: t("navExpansion"),
            shortLabel: t("navExpansionShort"),
            icon: Calculator,
            ownerOnly: true,
            matchPath: "/analytics",
            matchTab: "simulator",
          },
          { to: "/settings", label: t("navSettings"), shortLabel: t("navSettingsShort"), icon: Settings, ownerOnly: true, matchPath: "/settings" },
          { to: "/audit-log", label: t("navAudit"), shortLabel: t("navAuditShort"), icon: History, ownerOnly: true, matchPath: "/audit-log" },
        ],
      },
    ];

    return raw
      .filter((sec) => !sec.ownerOnly || isOwner)
      .map((sec) => ({
        ...sec,
        items: sec.items.filter((it) => !it.ownerOnly || isOwner),
      }))
      .filter((sec) => sec.items.length > 0);
  }, [isOwner, t]);

  const currentTab = new URLSearchParams(location.search).get("tab") || "forecast";

  const isItemActive = (item: SubNavItem): boolean => {
    if (location.pathname !== item.matchPath) return false;
    if (item.matchPath === "/analytics") {
      return currentTab === (item.matchTab || "forecast");
    }
    return true;
  };

  const activeSection =
    sections.find((s) => s.items.some((it) => isItemActive(it))) ?? sections[0];

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    daily: true,
    money: true,
    tools: true,
  });

  const toggleGroup = (id: string) => {
    setOpenGroups((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 text-slate-900">
      {/* Desktop / Laptop Left Sidebar — 3 Main Sections with Sub-Sections */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 bg-slate-900 text-slate-100 no-print">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center gap-3">
          <Factory className="w-7 h-7 text-amber-400 shrink-0" />
          <div className="min-w-0">
            <div className="font-bold tracking-tight text-lg">{t("appTitle")}</div>
            <div className="text-xs text-slate-400 truncate">
              {setupStatus?.unit_name && setupStatus.unit_name !== "LOOMOS" && setupStatus.unit_name !== t("appTitle")
                ? setupStatus.unit_name
                : t("appSubtitle")}
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5 select-none">
          {sections.map((section) => {
            const SectionIcon = section.icon;
            const isOpen = openGroups[section.id] ?? true;
            const hasActive = section.items.some((it) => isItemActive(it));

            return (
              <div key={section.id} className="space-y-1">
                <button
                  type="button"
                  onClick={() => toggleGroup(section.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider cursor-pointer transition ${
                    hasActive ? "text-amber-300 bg-slate-800/70" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <SectionIcon className="w-3.5 h-3.5" />
                    {section.title}
                  </span>
                  {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>

                {isOpen && (
                  <div className="pl-2 space-y-0.5">
                    {section.items.map((item) => {
                      const Icon = item.icon;
                      const active = isItemActive(item);
                      return (
                        <Link
                          key={item.to}
                          to={item.to}
                          className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
                            active
                              ? "bg-amber-500 text-slate-950 font-semibold shadow-sm"
                              : "text-slate-300 hover:bg-slate-800 hover:text-white"
                          }`}
                        >
                          <Icon className="w-4 h-4 shrink-0" />
                          <span className="truncate">{item.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between text-xs text-slate-300">
            <span className="truncate font-medium">
              {user?.full_name} ({user?.role ? t(`role_${user.role}`) : ""})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void toggleLanguage()}
              className="flex-1 py-1.5 px-2.5 rounded border border-slate-700 text-xs font-semibold hover:bg-slate-800 cursor-pointer"
            >
              {lang === "en" ? "EN | தமிழ்" : "தமிழ் | EN"}
            </button>
            <button
              type="button"
              onClick={logout}
              className="py-1.5 px-2.5 rounded bg-slate-800 hover:bg-rose-700 text-xs flex items-center gap-1 cursor-pointer"
              title={t("logout")}
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Top Header */}
      <header className="md:hidden sticky top-0 z-20 bg-slate-900 text-white px-4 py-3 flex items-center justify-between shadow no-print">
        <div className="flex items-center gap-2 min-w-0">
          <Factory className="w-5 h-5 text-amber-400 shrink-0" />
          <span className="font-bold text-base truncate">
            {setupStatus?.unit_name && setupStatus.unit_name !== "LOOMOS" ? setupStatus.unit_name : t("appTitle")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void toggleLanguage()}
            className="px-2.5 py-1 rounded border border-slate-700 text-xs font-semibold"
          >
            {lang === "en" ? "தமிழ்" : "EN"}
          </button>
          <button
            type="button"
            onClick={logout}
            className="p-1.5 rounded bg-slate-800"
            aria-label={t("logout")}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Mobile Sub-Section Pill Bar (for active Main Section) */}
      {activeSection && (
        <div className="md:hidden bg-white border-b border-slate-200 px-3 py-2 flex items-center gap-1.5 overflow-x-auto no-print select-none">
          {activeSection.items.map((item) => {
            const Icon = item.icon;
            const active = isItemActive(item);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold shrink-0 transition ${
                  active
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {item.shortLabel}
              </Link>
            );
          })}
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 md:pl-64 pb-20 md:pb-8 flex flex-col">
        <DemoBanner />
        <div className="max-w-6xl w-full mx-auto p-4 md:p-6">{children}</div>
      </main>

      {/* Mobile Bottom Nav — 3 Clean Main Sections */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-slate-200 grid no-print py-1.5 px-2 select-none"
        style={{ gridTemplateColumns: `repeat(${sections.length}, minmax(0, 1fr))` }}
      >
        {sections.map((section) => {
          const Icon = section.icon;
          const isCurrent = activeSection?.id === section.id;
          const firstTarget = section.items[0]?.to ?? "/dashboard";
          return (
            <Link
              key={section.id}
              to={firstTarget}
              className={`flex flex-col items-center justify-center gap-0.5 py-1 rounded-lg text-[11px] font-bold transition ${
                isCurrent ? "text-amber-600 bg-amber-50/70" : "text-slate-500"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{section.title}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

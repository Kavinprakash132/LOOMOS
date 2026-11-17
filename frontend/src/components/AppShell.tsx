import React from "react";
import { NavLink } from "react-router-dom";
import { BarChart3, ClipboardCheck, Camera, History, Layers, LogOut, Settings, Factory, Truck, Wallet } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { DemoBanner } from "./DemoBanner";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, setupStatus, lang, t, toggleLanguage, logout } = useAuth();

  const navItems = [
    { to: "/dashboard", label: t("navDashboard"), icon: BarChart3, ownerOnly: false },
    { to: "/today", label: t("navToday"), icon: ClipboardCheck, ownerOnly: false },
    { to: "/beams", label: t("navBeams"), icon: Layers, ownerOnly: false },
    { to: "/payroll", label: t("navPayroll"), icon: Wallet, ownerOnly: true },
    { to: "/deliveries", label: t("navDeliveries"), icon: Truck, ownerOnly: true },
    { to: "/inspect", label: t("navInspect"), icon: Camera, ownerOnly: false },
    { to: "/settings", label: t("navSettings"), icon: Settings, ownerOnly: true },
    { to: "/audit-log", label: t("navAudit"), icon: History, ownerOnly: true },
  ].filter((item) => !item.ownerOnly || user?.role === "OWNER");

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 text-slate-900">
      {/* Desktop / Laptop Left Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 bg-slate-900 text-slate-100 no-print">
        <div className="px-5 py-5 border-b border-slate-800 flex items-center gap-3">
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

        <nav className="flex-1 px-3 py-4 space-y-1 select-none">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? "bg-amber-500 text-slate-950"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-300">
            <span className="truncate font-medium">
              {user?.full_name} ({user?.role})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void toggleLanguage()}
              className="flex-1 py-1.5 px-2.5 rounded border border-slate-700 text-xs font-semibold hover:bg-slate-800"
            >
              {lang === "en" ? "EN | தமிழ்" : "தமிழ் | EN"}
            </button>
            <button
              type="button"
              onClick={logout}
              className="py-1.5 px-2.5 rounded bg-slate-800 hover:bg-rose-700 text-xs flex items-center gap-1"
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
          <span className="font-bold text-base truncate">{setupStatus?.unit_name ?? t("appTitle")}</span>
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

      {/* Main Content */}
      <main className="flex-1 md:pl-64 pb-20 md:pb-8 flex flex-col">
        <DemoBanner />
        <div className="max-w-6xl w-full mx-auto p-4 md:p-6">{children}</div>
      </main>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-slate-200 flex overflow-x-auto no-print py-1.5 px-1 select-none">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center shrink-0 min-w-[68px] gap-0.5 px-1.5 py-1 text-[10px] font-medium ${
                  isActive ? "text-amber-600" : "text-slate-500"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              <span className="truncate max-w-[68px]">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}

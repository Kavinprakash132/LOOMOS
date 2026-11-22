import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";

const AuditLogPage = lazy(() => import("./pages/AuditLogPage").then((m) => ({ default: m.AuditLogPage })));
const AnalyticsReportsPage = lazy(() =>
  import("./pages/AnalyticsReportsPage").then((m) => ({ default: m.AnalyticsReportsPage }))
);
const BeamsPage = lazy(() => import("./pages/BeamsPage").then((m) => ({ default: m.BeamsPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const DeliveriesPage = lazy(() => import("./pages/DeliveriesPage").then((m) => ({ default: m.DeliveriesPage })));
const InspectPage = lazy(() => import("./pages/InspectPage").then((m) => ({ default: m.InspectPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const PayrollPage = lazy(() => import("./pages/PayrollPage").then((m) => ({ default: m.PayrollPage })));
const SettingsMastersPage = lazy(() =>
  import("./pages/SettingsMastersPage").then((m) => ({ default: m.SettingsMastersPage }))
);
const SetupPage = lazy(() => import("./pages/SetupPage").then((m) => ({ default: m.SetupPage })));
const TodayShiftPage = lazy(() => import("./pages/TodayShiftPage").then((m) => ({ default: m.TodayShiftPage })));

function PageLoader() {
  const { tr } = useAuth();
  return (
    <div className="min-h-[40vh] flex items-center justify-center text-xs text-slate-500">
      {tr("Loading page...", "பக்கம் ஏற்றப்படுகிறது...")}
    </div>
  );
}

function AppRoutes() {
  const { loading, backendError, setupStatus, user, tr, refreshState } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-sm text-slate-600">
        {tr("Loading LOOMOS...", "லூமோஸ் ஏற்றப்படுகிறது...")}
      </div>
    );
  }

  if (backendError || !setupStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-3 text-center">
          <h1 className="text-base font-bold text-slate-900">
            {tr("Connecting to LOOMOS Backend...", "LOOMOS சேவையகத்துடன் இணைக்கப்படுகிறது...")}
          </h1>
          <p className="text-xs text-slate-600">
            {backendError ??
              tr(
                "Server is still starting up. Wait a couple seconds and tap Retry.",
                "சேவையகம் தொடங்கப்படுகிறது. சில விநாடிகள் காத்திருந்து மீண்டும் முயற்சிக்கவும்."
              )}
          </p>
          <button
            type="button"
            onClick={() => void refreshState()}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold cursor-pointer"
          >
            {tr("Retry Connection", "மீண்டும் இணைக்கவும்")}
          </button>
        </div>
      </div>
    );
  }

  if (!setupStatus.is_initialized) {
    return (
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/setup" element={<SetupPage />} />
          <Route path="*" element={<Navigate to="/setup" replace />} />
        </Routes>
      </Suspense>
    );
  }

  if (!user) {
    return (
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    );
  }

  const defaultRoute = user.role === "OWNER" ? "/dashboard" : "/today";

  return (
    <AppShell>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/today" element={<TodayShiftPage />} />
          <Route path="/beams" element={<BeamsPage />} />
          <Route path="/analytics" element={<AnalyticsReportsPage />} />
          <Route path="/inspect" element={<InspectPage />} />
          {user.role === "OWNER" && (
            <>
              <Route path="/payroll" element={<PayrollPage />} />
              <Route path="/deliveries" element={<DeliveriesPage />} />
              <Route path="/settings" element={<SettingsMastersPage />} />
              <Route path="/audit-log" element={<AuditLogPage />} />
            </>
          )}
          <Route path="*" element={<Navigate to={defaultRoute} replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}

export function App() {
  useEffect(() => {
    const markInvalidForm = (event: Event) => {
      const target = event.target;
      if (target instanceof HTMLElement) {
        const form = target.closest("form");
        if (form) form.classList.add("was-validated");
      }
    };
    const handleFormSubmit = (event: Event) => {
      const target = event.target;
      if (target instanceof HTMLFormElement) {
        if (target.checkValidity()) {
          target.classList.remove("was-validated");
        } else {
          target.classList.add("was-validated");
        }
      }
    };
    document.addEventListener("invalid", markInvalidForm, true);
    document.addEventListener("submit", handleFormSubmit, true);
    return () => {
      document.removeEventListener("invalid", markInvalidForm, true);
      document.removeEventListener("submit", handleFormSubmit, true);
    };
  }, []);

  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}

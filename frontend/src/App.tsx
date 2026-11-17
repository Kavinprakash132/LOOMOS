import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AuditLogPage } from "./pages/AuditLogPage";
import { BeamsPage } from "./pages/BeamsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeliveriesPage } from "./pages/DeliveriesPage";
import { InspectPage } from "./pages/InspectPage";
import { LoginPage } from "./pages/LoginPage";
import { PayrollPage } from "./pages/PayrollPage";
import { SettingsMastersPage } from "./pages/SettingsMastersPage";
import { SetupPage } from "./pages/SetupPage";
import { TodayShiftPage } from "./pages/TodayShiftPage";

function AppRoutes() {
  const { loading, backendError, setupStatus, user, t, refreshState } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-sm text-slate-600">
        Loading LOOMOS...
      </div>
    );
  }

  if (backendError || !setupStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-3 text-center">
          <h1 className="text-base font-bold text-slate-900">Connecting to LOOMOS Backend...</h1>
          <p className="text-xs text-slate-600">
            {backendError ?? "Server is still starting up. Wait a couple seconds and tap Retry."}
          </p>
          <button
            type="button"
            onClick={() => void refreshState()}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!setupStatus.is_initialized) {
    return (
      <Routes>
        <Route path="/setup" element={<SetupPage />} />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  const defaultRoute = user.role === "OWNER" ? "/dashboard" : "/today";

  return (
    <AppShell>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/today" element={<TodayShiftPage />} />
        <Route path="/beams" element={<BeamsPage />} />
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
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

import React, { useState } from "react";
import { Factory } from "lucide-react";
import { apiRequest } from "../api/client";
import { DemoBanner } from "../components/DemoBanner";
import { PasswordInput } from "../components/PasswordInput";
import { useAuth } from "../context/AuthContext";
import { AuthTokenResponse } from "../types/api";

export function LoginPage() {
  const { setupStatus, lang, t, toggleLanguage, completeAuth } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const usernameMissing = attemptedSubmit && username.trim().length === 0;
  const passwordMissing = attemptedSubmit && password.length === 0;
  const displayError = error ?? (usernameMissing || passwordMissing ? t("fillRequiredFields") : null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttemptedSubmit(true);
    setError(null);
    if (username.trim().length === 0 || password.length === 0) {
      return;
    }
    setLoading(true);
    try {
      const resp = await apiRequest<AuthTokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      completeAuth(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      <DemoBanner />
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
        <div className="bg-slate-900 text-white px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Factory className="w-7 h-7 text-amber-400" />
            <div>
              <h1 className="font-bold text-lg">
                {setupStatus?.unit_name && setupStatus.unit_name !== "LOOMOS" ? setupStatus.unit_name : t("appTitle")}
              </h1>
              <p className="text-xs text-slate-300">{t("loginTitle")}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void toggleLanguage()}
            className="px-2.5 py-1 rounded border border-slate-700 text-xs font-semibold"
          >
            {lang === "en" ? "தமிழ்" : "EN"}
          </button>
        </div>

        <form noValidate onSubmit={handleSubmit} className="p-6 space-y-4">
          {displayError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
              {displayError}
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">
              {t("username")} <span className="text-rose-600">*</span>
            </label>
            <input
              type="text"
              required
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={`w-full px-3 py-2.5 rounded-lg border text-sm ${
                usernameMissing ? "field-invalid" : "border-slate-300"
              }`}
            />
            {usernameMissing && <p className="mt-1 text-xs text-rose-600 font-medium">{t("usernameRequired")}</p>}
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">
              {t("loginPassword")} <span className="text-rose-600">*</span>
            </label>
            <PasswordInput
              required
              autoComplete="current-password"
              showLabel={t("showPassword")}
              hideLabel={t("hidePassword")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`w-full px-3 py-2.5 rounded-lg border text-sm ${
                passwordMissing ? "field-invalid" : "border-slate-300"
              }`}
            />
            {passwordMissing && <p className="mt-1 text-xs text-rose-600 font-medium">{t("passwordRequired")}</p>}
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-sm disabled:opacity-60"
          >
            {loading ? "..." : t("loginBtn")}
          </button>
        </form>
        </div>
      </div>
    </div>
  );
}

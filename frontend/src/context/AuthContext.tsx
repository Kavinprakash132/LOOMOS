import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiRequest, getStoredToken, setStoredToken } from "../api/client";
import { UI_STRINGS } from "../i18n/translations";
import { AuthTokenResponse, LangCode, SetupStatus, User } from "../types/api";

interface AuthContextValue {
  loading: boolean;
  backendError: string | null;
  setupStatus: SetupStatus | null;
  user: User | null;
  lang: LangCode;
  t: (key: string) => string;
  tr: (en: string, ta: string) => string;
  refreshState: () => Promise<void>;
  completeAuth: (resp: AuthTokenResponse) => void;
  logout: () => void;
  toggleLanguage: (nextLang?: LangCode) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [lang, setLang] = useState<LangCode>(
    () => (localStorage.getItem("loomos_lang") as LangCode) || "en"
  );

  const refreshState = useCallback(async () => {
    setLoading(true);
    setBackendError(null);
    try {
      const status = await apiRequest<SetupStatus>("/setup/status");
      setSetupStatus(status);
      if (status.is_initialized && getStoredToken()) {
        try {
          const me = await apiRequest<User>("/auth/me");
          setUser(me);
          setLang(me.preferred_lang);
          localStorage.setItem("loomos_lang", me.preferred_lang);
        } catch {
          setStoredToken(null);
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : "LOOMOS server is not reachable yet.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshState();
  }, [refreshState]);

  const completeAuth = useCallback((resp: AuthTokenResponse) => {
    setStoredToken(resp.access_token);
    setUser(resp.user);
    setLang(resp.user.preferred_lang);
    localStorage.setItem("loomos_lang", resp.user.preferred_lang);
    setSetupStatus((prev) =>
      prev
        ? { ...prev, is_initialized: true }
        : {
            is_initialized: true,
            unit_name: null,
            loom_count: 0,
            is_demo_mode: false,
            active_db_name: "loomos.db",
          }
    );
  }, []);

  const logout = useCallback(() => {
    setStoredToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setStoredToken(null);
      setUser(null);
    };
    window.addEventListener("loomos:unauthorized", onUnauthorized);
    return () => window.removeEventListener("loomos:unauthorized", onUnauthorized);
  }, []);

  const toggleLanguage = useCallback(
    async (explicit?: LangCode) => {
      const next: LangCode = explicit ?? (lang === "en" ? "ta" : "en");
      setLang(next);
      localStorage.setItem("loomos_lang", next);
      if (user && getStoredToken()) {
        try {
          const updated = await apiRequest<User>("/auth/me/language", {
            method: "PATCH",
            body: JSON.stringify({ preferred_lang: next }),
          });
          setUser(updated);
        } catch {
          // Keep local preference even if offline
        }
      }
    },
    [lang, user]
  );

  const t = useCallback(
    (key: string) => UI_STRINGS[lang]?.[key] ?? UI_STRINGS.en[key] ?? key,
    [lang]
  );

  const tr = useCallback((en: string, ta: string) => (lang === "ta" ? ta : en), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <AuthContext.Provider
      value={{ loading, backendError, setupStatus, user, lang, t, tr, refreshState, completeAuth, logout, toggleLanguage }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

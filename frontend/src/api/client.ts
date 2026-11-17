const TOKEN_STORAGE_KEY = "loomos_jwt_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers ?? {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      } else if (Array.isArray(data?.detail)) {
        detail = data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
      }
    } catch {
      // Fallback to status text
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export function formatRupeesFromPaise(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

/** Format YYYY-MM-DD (or ISO prefix) as Indian DD/MM/YYYY for UI display. */
export function formatDateDMY(isoDate: string | null | undefined): string {
  if (!isoDate) return "-";
  const datePart = isoDate.slice(0, 10);
  const parts = datePart.split("-");
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

/** Format minutes as HH.MM shift hours (e.g. 1400 mins -> "23.20", 1440 mins -> "24.00"). */
export function formatHoursFromMins(totalMins: number): string {
  const safe = Math.max(0, Math.round(totalMins));
  const hrs = Math.floor(safe / 60);
  const remMins = safe % 60;
  return `${hrs}.${String(remMins).padStart(2, "0")}`;
}

/** Format UTC ISO timestamp into local IST (DD/MM/YYYY, HH:MM am/pm). */
export function formatDateTimeIST(isoTimestamp: string): string {
  const normalized = /Z$|[+-]\d{2}:\d{2}$/.test(isoTimestamp) ? isoTimestamp : `${isoTimestamp}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return isoTimestamp;
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function localIsoDate(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function offsetLocalIsoDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return localIsoDate(d);
}

export function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `uuid-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export async function downloadProtectedFile(path: string, fallbackFilename: string): Promise<void> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api/v1${path}`, { headers });
  if (!res.ok) {
    throw new ApiError(res.status, `Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const disp = res.headers.get("Content-Disposition") ?? "";
  const match = disp.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? fallbackFilename;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

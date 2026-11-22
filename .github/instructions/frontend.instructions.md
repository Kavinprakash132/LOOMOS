---
applyTo: "frontend/**"
---
# LOOMOS Frontend Coding & UI/UX Guidelines (React + TypeScript + Tailwind v4)

## Visual & UX Design Principles
- **Calm, Professional, Zero Clutter:** Never create "option inside options" (no nested collapsible sidebar trees, no repeated mode switches on every card, no giant permanent help banners).
- **Data First:** Lists and tables appear immediately at the top of pages and Settings tabs. Hide creation forms behind a single clear **`+ Add ...`** toggle button, and auto-close the form on successful save.
- **Unified Tabs:** Use clean underline tabs (`border-b-2 -mb-px`) matching `TodayShiftPage`, `SettingsMastersPage`, `PayrollPage`, `DeliveriesPage`, and `AnalyticsReportsPage`.
- **Guide Banners:** Always use `<PageGuideBanner />`, which stays collapsed by default until the user clicks `? Guide`.
- **Inline Optional Details:** Tuck rare or optional inputs (like shift beam override, defective metres, or mid-shift 2nd beam split) inside a single collapsed `More options` disclosure per card.

## Required App Infrastructure Hooks
1. **Global Toasts (`useToast()`):** Every create, save, edit, mount/unload, finalize, dismiss, or delete handler MUST call `toast.success(...)` on success and `toast.error(...)` on failure. Never use `window.alert` or `window.confirm` (use `ConfirmVoidModal` for destructive actions).
2. **Live Auto-Refresh (`useLiveRefresh(loadFn)`):** Every data page MUST subscribe via `useLiveRefresh` so confirmed LOOMOS AI Copilot actions update the active page automatically without requiring a browser reload.
3. **API Client & Formatters (`src/api/client.ts`):**
   - Always use `apiRequest<T>(...)` (automatically attaches JWT and handles `401`).
   - Always format dates with `formatDateDMY` (`DD/MM/YYYY`), timestamps with `formatDateTimeIST`, and money with `formatRupeesFromPaise`.
   - Always use `localIsoDate()` / `offsetLocalIsoDate(...)` instead of `new Date().toISOString().slice(0, 10)` so IST dates never shift around midnight.

## Bilingual & Mobile Requirements
- Every visible label, heading, placeholder, button, empty state, and toast MUST support English & Tamil via `t("key")` or `tr("English", "தமிழ்")` from `useAuth()`.
- Keep pages lazy-loaded in `src/App.tsx`.
- Keep photo upload controls dual-button: Camera (`capture="environment"`) + Gallery/Files (no `capture` attribute).
- Always run `npm run build` (`tsc -b && vite build`) and fix all TypeScript strict errors before finishing.

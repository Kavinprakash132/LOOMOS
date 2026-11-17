import React, { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmVoidModalProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  defaultReason?: string;
  requireReason?: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => Promise<void> | void;
}

/** Accessible in-app confirmation modal replacing browser window.prompt for reliable Void/Remove actions. */
export function ConfirmVoidModal({
  open,
  title,
  description,
  confirmLabel = "Confirm Void / Remove",
  defaultReason = "Entry mistake",
  requireReason = true,
  onCancel,
  onConfirm,
}: ConfirmVoidModalProps) {
  const [reason, setReason] = useState(defaultReason);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setReason(defaultReason);
      setTouched(false);
      setBusy(false);
    }
  }, [open, defaultReason]);

  if (!open) return null;

  const invalid = requireReason && touched && reason.trim().length < 2;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (requireReason && reason.trim().length < 2) return;
    setBusy(true);
    try {
      await onConfirm(reason.trim());
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4 no-print">
      <div className="bg-white rounded-2xl max-w-md w-full p-5 shadow-2xl border border-slate-200 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 text-rose-700 font-bold text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{title}</span>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="text-slate-400 hover:text-slate-700 p-0.5"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {description && <p className="text-xs text-slate-600">{description}</p>}

        <form noValidate onSubmit={handleSubmit} className="space-y-3">
          {requireReason && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason (saved in Change History) <span className="text-rose-600">*</span>
              </label>
              <input
                type="text"
                autoFocus
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Entry mistake, duplicate entry"
                className={`w-full px-3 py-2 rounded-lg border text-sm ${
                  invalid ? "field-invalid" : "border-slate-300"
                }`}
              />
              {invalid && (
                <p className="mt-1 text-xs text-rose-600 font-medium">Enter at least 2 characters.</p>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="px-3.5 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold disabled:opacity-50"
            >
              {busy ? "Removing..." : confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

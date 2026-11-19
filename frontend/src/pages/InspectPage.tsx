import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, Cpu, Eye, Upload } from "lucide-react";
import { apiRequest, formatDateTimeIST } from "../api/client";
import { PageGuideBanner } from "../components/PageGuideBanner";
import { TechnicalDetailsToggle } from "../components/TechnicalDetailsToggle";
import { Beam, InspectionRecord, Loom, ModelCardResponse, Weaver } from "../types/api";

const DEFECT_LABEL_OPTIONS = [
  "Broken End (Warp)",
  "Broken Yarn",
  "Broken Pick (Weft)",
  "Fuzzyball / Knot",
  "Cut Selvage",
  "Weft Crack",
  "Warp Ball / Nep",
  "Oil / Stain",
  "Crease",
  "Other Cloth Defect",
];

export function InspectPage() {
  const [card, setCard] = useState<ModelCardResponse | null>(null);
  const [inspections, setInspections] = useState<InspectionRecord[]>([]);
  const [looms, setLooms] = useState<Loom[]>([]);
  const [beams, setBeams] = useState<Beam[]>([]);
  const [weavers, setWeavers] = useState<Weaver[]>([]);

  const [selectedLoomId, setSelectedLoomId] = useState<string>("");
  const [selectedBeamId, setSelectedBeamId] = useState<string>("");
  const [selectedWeaverId, setSelectedWeaverId] = useState<string>("");

  const [active, setActive] = useState<InspectionRecord | null>(null);
  const [viewMode, setViewMode] = useState<"heatmap" | "side" | "raw">("heatmap");
  const [reviewStatus, setReviewStatus] = useState<"CONFIRMED_DEFECT" | "CONFIRMED_CLEAN">("CONFIRMED_DEFECT");
  const [reviewLabel, setReviewLabel] = useState<string>(DEFECT_LABEL_OPTIONS[0]);
  const [defectiveMetres, setDefectiveMetres] = useState<string>("0.50");
  const [addToShift, setAddToShift] = useState<boolean>(false);

  const [analyzing, setAnalyzing] = useState(false);
  const [savingReview, setSavingReview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const syncReviewDefaults = useCallback((rec: InspectionRecord) => {
    const flagged = rec.prediction?.predicted_label === "Defect Flagged" || rec.review_status === "CONFIRMED_DEFECT";
    setReviewStatus(rec.review_status === "CONFIRMED_CLEAN" ? "CONFIRMED_CLEAN" : flagged ? "CONFIRMED_DEFECT" : "CONFIRMED_CLEAN");
    if (rec.reviewed_label && DEFECT_LABEL_OPTIONS.includes(rec.reviewed_label)) {
      setReviewLabel(rec.reviewed_label);
    } else {
      setReviewLabel(DEFECT_LABEL_OPTIONS[0]);
    }
    setDefectiveMetres(Number(rec.defective_metres) > 0 ? rec.defective_metres : flagged ? "0.50" : "0.00");
    setAddToShift(Boolean(rec.loom_id && flagged));
  }, []);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [mc, list, lm, bm, wv] = await Promise.all([
        apiRequest<ModelCardResponse>("/inspections/model-card"),
        apiRequest<InspectionRecord[]>("/inspections?limit=30"),
        apiRequest<Loom[]>("/looms"),
        apiRequest<Beam[]>("/beams"),
        apiRequest<Weaver[]>("/weavers"),
      ]);
      setCard(mc);
      setInspections(list);
      setLooms(lm.filter((l) => l.is_active));
      setBeams(bm);
      setWeavers(wv);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inspection workspace");
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const runAnalyze = async ({ file, sampleId }: { file?: File; sampleId?: string }) => {
    setError(null);
    setSuccess(null);
    setAnalyzing(true);
    try {
      const fd = new FormData();
      if (file) fd.append("file", file);
      if (sampleId) fd.append("sample_id", sampleId);
      if (selectedLoomId) fd.append("loom_id", selectedLoomId);
      if (selectedBeamId) fd.append("beam_id", selectedBeamId);
      if (selectedWeaverId) fd.append("weaver_id", selectedWeaverId);

      const rec = await apiRequest<InspectionRecord>("/inspections/analyze", {
        method: "POST",
        body: fd,
      });
      setActive(rec);
      setViewMode("heatmap");
      syncReviewDefaults(rec);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze cloth photo");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void runAnalyze({ file });
    e.target.value = "";
  };

  const handleSaveReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!active) return;
    setError(null);
    setSuccess(null);
    setSavingReview(true);
    try {
      const updated = await apiRequest<InspectionRecord>(`/inspections/${active.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          review_status: reviewStatus,
          reviewed_label: reviewStatus === "CONFIRMED_CLEAN" ? "Clean Cloth" : reviewLabel,
          defective_metres: reviewStatus === "CONFIRMED_DEFECT" ? defectiveMetres || "0" : "0",
          loom_id: selectedLoomId ? Number(selectedLoomId) : active.loom_id,
          beam_id: selectedBeamId ? Number(selectedBeamId) : active.beam_id,
          weaver_id: selectedWeaverId ? Number(selectedWeaverId) : active.weaver_id,
          add_to_today_shift: reviewStatus === "CONFIRMED_DEFECT" && addToShift,
        }),
      });
      setActive(updated);
      setSuccess(
        reviewStatus === "CONFIRMED_DEFECT"
          ? `Saved Confirmed Defect (${updated.reviewed_label})${
              updated.shift_entry_id ? " and updated shift defective metres." : "."
            }`
          : "Saved Confirmed Clean Cloth photo for dataset tracking."
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save inspection review");
    } finally {
      setSavingReview(false);
    }
  };

  const defectCount = inspections.filter((i) => i.review_status === "CONFIRMED_DEFECT").length;
  const cleanCount = inspections.filter((i) => i.review_status === "CONFIRMED_CLEAN").length;
  const winnerStats = card?.comparison.find((c) => c.arch === card.architecture) ?? card?.comparison[0];

  return (
    <div className="space-y-5 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Camera className="w-5 h-5 text-amber-600" />
            Cloth Quality Audit &amp; AI Defect Inspection
          </h1>
          <p className="text-xs text-slate-500">
            Take or upload a loom cloth photo, inspect the Grad-CAM defect highlight map, and confirm Clean or Defect (saves every checked photo).
          </p>
        </div>
      </div>

      {error && <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>}
      {success && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">{success}</div>}

      <PageGuideBanner
        steps={[
          "Take or upload a cloth photo (or tap a sample)",
          "Check where the AI highlights possible defects",
          "Confirm Defect or Clean Cloth to save",
        ]}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Photos Checked</div>
          <div className="text-xl font-bold">{inspections.length}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Confirmed Defects</div>
          <div className="text-xl font-bold text-rose-600">{defectCount}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500">Confirmed Clean</div>
          <div className="text-xl font-bold text-emerald-700">{cleanCount}</div>
        </div>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200">
          <div className="text-xs text-slate-500 flex items-center gap-1">
            <Cpu className="w-3.5 h-3.5 text-amber-600" /> Active ONNX Model
          </div>
          <div className="text-sm font-bold text-slate-900 mt-0.5 truncate">
            {card ? card.winning_model_name : "Loading..."}
          </div>
          <div className="text-[11px] text-slate-500">
            {winnerStats ? `CPU ~${winnerStats.inference_ms} ms/img · F1 ${winnerStats.defect_f1}` : ""}
          </div>
        </div>
      </div>

      {/* Step 1: Upload Photo or Pick Reference Sample */}
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
          <h2 className="text-sm font-bold">1. Upload / Capture Cloth Photo</h2>
          <div className="grid sm:grid-cols-3 gap-2">
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Shuttle Loom (optional)</label>
              <select
                value={selectedLoomId}
                onChange={(e) => setSelectedLoomId(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
              >
                <option value="">-- Any Loom --</option>
                {looms.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.loom_number} ({l.rated_rpm} RPM)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Warp Beam (optional)</label>
              <select
                value={selectedBeamId}
                onChange={(e) => setSelectedBeamId(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
              >
                <option value="">-- Any Beam --</option>
                {beams.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.beam_no} ({b.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Weaver (optional)</label>
              <select
                value={selectedWeaverId}
                onChange={(e) => setSelectedWeaverId(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
              >
                <option value="">-- Any Weaver --</option>
                {weavers.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.full_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl p-5 text-center hover:border-amber-500 hover:bg-amber-50/40 cursor-pointer transition">
            <Upload className="w-6 h-6 text-amber-600 mb-1.5" />
            <span className="text-xs font-bold text-slate-800">
              {analyzing ? "Running AI Inspection..." : "Tap to Take Photo or Choose Cloth Image"}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5">
              Supports phone camera JPG / PNG — runs offline on shed CPU in milliseconds
            </span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              disabled={analyzing}
              onChange={handleFileChange}
              className="hidden"
            />
          </label>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-bold">AITEX Reference Sample (demo only)</h2>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">
              Held-Out Test Set
            </span>
          </div>
          <p className="text-[11px] text-slate-500">
            Click any held-out textile sample below to test live ONNX detection &amp; Grad-CAM heatmaps right away:
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {card?.samples.map((s) => (
              <button
                key={s.id}
                type="button"
                disabled={analyzing}
                onClick={() => void runAnalyze({ sampleId: s.id })}
                className="text-left rounded-lg border border-slate-200 hover:border-amber-500 p-1.5 bg-slate-50 hover:bg-amber-50/40 transition cursor-pointer disabled:opacity-50"
              >
                <img
                  src={s.image_url}
                  alt={s.title}
                  className="w-full h-16 object-cover rounded border border-slate-200 mb-1"
                />
                <div className="text-[11px] font-bold text-slate-800 truncate">{s.ground_truth_label}</div>
                <div
                  className={`text-[10px] font-semibold ${
                    s.is_defect ? "text-rose-700" : "text-emerald-700"
                  }`}
                >
                  {s.is_defect ? "Defect Sample" : "Clean Sample"}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Step 2: Active AI Result + Grad-CAM + Human Review */}
      {active && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-bold flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-amber-600" />
                Inspection #{active.id} — AI Heatmap &amp; Review
              </h2>
              {active.prediction && (
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    active.prediction.predicted_label === "Defect Flagged"
                      ? "bg-rose-100 text-rose-800"
                      : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {active.prediction.predicted_label} ({(active.prediction.confidence * 100).toFixed(1)}%)
                </span>
              )}
              {active.prediction?.is_uncertain && (
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-[11px] font-semibold">
                  Borderline — Verify Visually
                </span>
              )}
            </div>

            <div className="inline-flex rounded-lg border border-slate-300 bg-slate-100 p-0.5 text-xs font-semibold">
              {[
                { id: "heatmap", label: "Heatmap Overlay" },
                { id: "side", label: "Side-by-Side" },
                { id: "raw", label: "Original Cloth" },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setViewMode(m.id as "heatmap" | "side" | "raw")}
                  className={`px-2.5 py-1 rounded-md cursor-pointer ${
                    viewMode === m.id ? "bg-slate-900 text-white" : "text-slate-700"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4 items-start">
            <div className="space-y-2">
              {viewMode === "side" ? (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-[11px] text-slate-500 mb-1">Original Photo</div>
                    <img src={active.raw_image_url} alt="Original cloth" className="w-full rounded-lg border border-slate-200" />
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-500 mb-1">Grad-CAM Focus</div>
                    <img
                      src={active.heatmap_image_url ?? active.raw_image_url}
                      alt="Grad-CAM overlay"
                      className="w-full rounded-lg border border-slate-200"
                    />
                  </div>
                </div>
              ) : (
                <img
                  src={viewMode === "heatmap" && active.heatmap_image_url ? active.heatmap_image_url : active.raw_image_url}
                  alt="Cloth inspection preview"
                  className="w-full max-w-sm rounded-xl border border-slate-200"
                />
              )}
              {active.prediction && (
                <div className="text-[11px] text-slate-500">
                  Model: <b>{active.prediction.model_version}</b> · Cutoff{" "}
                  {(active.prediction.threshold_used * 100).toFixed(0)}% · Ran in{" "}
                  <b>{active.prediction.inference_ms} ms</b>
                </div>
              )}
            </div>

            <form onSubmit={handleSaveReview} className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
              <div className="text-xs font-bold text-slate-800">Human Verification (Saves Photo for Audit &amp; Training)</div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setReviewStatus("CONFIRMED_CLEAN")}
                  className={`py-2 px-3 rounded-lg text-xs font-bold border cursor-pointer inline-flex items-center justify-center gap-1.5 ${
                    reviewStatus === "CONFIRMED_CLEAN"
                      ? "bg-emerald-700 text-white border-emerald-700"
                      : "bg-white text-slate-700 border-slate-300"
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4" /> Confirm Clean Cloth
                </button>
                <button
                  type="button"
                  onClick={() => setReviewStatus("CONFIRMED_DEFECT")}
                  className={`py-2 px-3 rounded-lg text-xs font-bold border cursor-pointer inline-flex items-center justify-center gap-1.5 ${
                    reviewStatus === "CONFIRMED_DEFECT"
                      ? "bg-rose-700 text-white border-rose-700"
                      : "bg-white text-slate-700 border-slate-300"
                  }`}
                >
                  <AlertTriangle className="w-4 h-4" /> Confirm Defect
                </button>
              </div>

              {reviewStatus === "CONFIRMED_DEFECT" && (
                <div className="space-y-2.5">
                  <div className="grid sm:grid-cols-2 gap-2">
                    <div>
                      <label className="text-[11px] font-medium text-slate-600 block mb-0.5">Defect Type *</label>
                      <select
                        value={reviewLabel}
                        onChange={(e) => setReviewLabel(e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
                      >
                        {DEFECT_LABEL_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-[11px] font-medium text-slate-600 block mb-0.5">
                        Damaged Cloth (m, optional)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={defectiveMetres}
                        onChange={(e) => setDefectiveMetres(e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded border border-slate-300 text-xs bg-white"
                      />
                    </div>
                  </div>
                  {(selectedLoomId || active.loom_id) && (
                    <label className="flex items-center gap-2 text-xs text-slate-700 font-medium">
                      <input
                        type="checkbox"
                        checked={addToShift}
                        onChange={(e) => setAddToShift(e.target.checked)}
                      />
                      Also add damaged metres to latest shift on selected loom (unlocks Dashboard Quality %)
                    </label>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={savingReview}
                className="w-full py-2 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold cursor-pointer disabled:opacity-50"
              >
                {savingReview ? "Saving Review..." : "Save Confirmed Review"}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Recent Reviewed Photos */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2.5">
        <h2 className="text-sm font-bold">Recent Cloth Inspections ({inspections.length})</h2>
        {inspections.length === 0 ? (
          <div className="text-xs text-slate-500 py-4">No cloth photos checked yet. Upload a photo or click a reference sample above.</div>
        ) : (
          <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
            {inspections.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActive(item);
                  syncReviewDefaults(item);
                }}
                className="w-full text-left py-2 flex items-center justify-between gap-2.5 hover:bg-slate-50 px-1.5 rounded cursor-pointer"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <img
                    src={item.heatmap_image_url ?? item.raw_image_url}
                    alt={`Inspection ${item.id}`}
                    className="w-10 h-10 rounded object-cover border border-slate-200 shrink-0"
                  />
                  <div className="min-w-0 text-xs">
                    <div className="font-bold text-slate-800 truncate">
                      #{item.id} · {item.reviewed_label ?? item.prediction?.predicted_label ?? "Pending"}
                      {item.loom_number ? ` (${item.loom_number})` : ""}
                    </div>
                    <div className="text-[11px] text-slate-500 truncate">
                      {formatDateTimeIST(item.inspected_at)}
                      {Number(item.defective_metres) > 0 ? ` · Damaged ${item.defective_metres} m` : ""}
                    </div>
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold shrink-0 ${
                    item.review_status === "CONFIRMED_DEFECT"
                      ? "bg-rose-100 text-rose-800"
                      : item.review_status === "CONFIRMED_CLEAN"
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {item.review_status === "CONFIRMED_DEFECT"
                    ? "Defect"
                    : item.review_status === "CONFIRMED_CLEAN"
                    ? "Clean"
                    : "Pending"}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Collapsible Thesis / Research AI Model Card */}
      {card && (
        <TechnicalDetailsToggle
          title="Show AI Accuracy & Thesis Model Card (ResNet-18 vs MobileNetV3)"
          subtitle="Held-out AITEX test comparison · Defect Recall, F1, Precision, ROC-AUC & CPU latency"
        >
          <p className="text-xs text-slate-600">{card.held_out_split_summary.imbalance_note}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-1.5 pr-2">Model</th>
                  <th className="py-1.5 pr-2">Defect Recall</th>
                  <th className="py-1.5 pr-2">Defect F1</th>
                  <th className="py-1.5 pr-2">Precision</th>
                  <th className="py-1.5 pr-2">ROC-AUC</th>
                  <th className="py-1.5">CPU ms</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {card.comparison.map((m) => (
                  <tr key={m.arch} className={m.arch === card.architecture ? "bg-amber-50/70 font-semibold" : ""}>
                    <td className="py-1.5 pr-2">
                      {m.name} {m.arch === card.architecture && <span className="text-[10px] text-amber-800">(Active)</span>}
                    </td>
                    <td className="py-1.5 pr-2">{m.defect_recall.toFixed(3)}</td>
                    <td className="py-1.5 pr-2">{m.defect_f1.toFixed(3)}</td>
                    <td className="py-1.5 pr-2">{m.defect_precision.toFixed(3)}</td>
                    <td className="py-1.5 pr-2">{m.roc_auc.toFixed(3)}</td>
                    <td className="py-1.5">{m.inference_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-[11px] text-slate-500">
            Strip split: {card.held_out_split_summary.train_strips} train / {card.held_out_split_summary.val_strips} val /{" "}
            {card.held_out_split_summary.test_strips} held-out test ({card.held_out_split_summary.test_defect_patches} defect,{" "}
            {card.held_out_split_summary.test_clean_patches} clean patches).
          </div>
        </TechnicalDetailsToggle>
      )}
    </div>
  );
}

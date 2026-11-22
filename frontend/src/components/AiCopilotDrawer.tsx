import React, { useEffect, useRef, useState } from "react";
import {
  Camera,
  CheckCircle2,
  ImagePlus,
  Loader2,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Wrench,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { AssistantChatResponse, ExecuteAiActionResponse, PendingAiAction } from "../types/api";

interface ActionState extends PendingAiAction {
  status: "pending" | "executing" | "executed" | "cancelled" | "error";
  feedback?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  imagePreviewUrl?: string;
  modelUsed?: string;
  toolsUsed?: string[];
  actions?: ActionState[];
  isError?: boolean;
}

function renderFormattedText(text: string): React.ReactNode {
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5 text-sm leading-relaxed break-words">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        // Render inline **bold** and `code` cleanly
        const renderInline = (raw: string) => {
          const parts = raw.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
          return parts.map((part, pIdx) => {
            if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
              return (
                <strong key={pIdx} className="font-semibold text-slate-900">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
              return (
                <code
                  key={pIdx}
                  className="px-1 py-0.5 rounded bg-slate-100 text-slate-800 text-xs font-mono"
                >
                  {part.slice(1, -1)}
                </code>
              );
            }
            return <React.Fragment key={pIdx}>{part}</React.Fragment>;
          });
        };

        if (/^[-*•]\s+/.test(trimmed)) {
          return (
            <div key={idx} className="flex items-start gap-1.5 pl-1">
              <span className="text-amber-600 font-bold leading-5">•</span>
              <span className="flex-1">{renderInline(trimmed.replace(/^[-*•]\s+/, ""))}</span>
            </div>
          );
        }
        if (/^#{1,3}\s+/.test(trimmed)) {
          return (
            <div key={idx} className="font-bold text-slate-900 pt-1">
              {renderInline(trimmed.replace(/^#{1,3}\s+/, ""))}
            </div>
          );
        }
        return <p key={idx}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

export default function AiCopilotDrawer() {
  const { user, lang, tr } = useAuth();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"fast" | "deep">("fast");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [attachedPreview, setAttachedPreview] = useState<string | null>(null);

  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, open]);

  useEffect(() => {
    return () => {
      if (attachedPreview) URL.revokeObjectURL(attachedPreview);
    };
  }, [attachedPreview]);

  if (!user?.ai_enabled) {
    return null;
  }

  const quickPrompts =
    lang === "ta"
      ? [
          "இன்றைய ஆலை சுருக்கம் & லாப நஷ்டம்",
          "ஓடும் பீம்கள் ETA & எச்சரிக்கைகள்",
          "EB மின்சாரம் & மீட்டர் ஆய்வு",
          "இந்த வார தொழிலாளர் கூலி கணக்கு",
          "வியாபாரி நிலுவை & ரேட் குறைப்பு சரிபார்",
        ]
      : [
          "Today's shed summary & P&L",
          "Running beam ETAs & open alerts",
          "Check EB efficiency & kWh/m",
          "This week weaver payroll preview",
          "Check trader dues & rate cuts",
        ];

  const handleFilePick = (file: File | null) => {
    if (!file) return;
    if (attachedPreview) URL.revokeObjectURL(attachedPreview);
    setAttachedFile(file);
    setAttachedPreview(URL.createObjectURL(file));
  };

  const clearAttachment = () => {
    if (attachedPreview) URL.revokeObjectURL(attachedPreview);
    setAttachedFile(null);
    setAttachedPreview(null);
    if (cameraInputRef.current) cameraInputRef.current.value = "";
    if (galleryInputRef.current) galleryInputRef.current.value = "";
  };

  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if ((!text && !attachedFile) || sending) return;

    const localImgUrl = attachedFile ? URL.createObjectURL(attachedFile) : undefined;
    const fileToSend = attachedFile;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text || tr("Analyze attached photo", "இணைத்த புகைப்படத்தை ஆய்வு செய்"),
      imagePreviewUrl: localImgUrl,
    };

    const historyPayload = messages.slice(-14).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMsg]);
    if (!overrideText) setInput("");
    clearAttachment();
    setSending(true);

    try {
      const form = new FormData();
      form.append("message", text);
      form.append("history_json", JSON.stringify(historyPayload));
      form.append("mode", mode);
      form.append("ui_lang", lang);
      if (fileToSend) {
        form.append("image", fileToSend);
      }

      const res = await apiRequest<AssistantChatResponse>("/assistant/chat", {
        method: "POST",
        body: form,
      });

      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: res.reply,
        modelUsed: res.model_used,
        toolsUsed: res.tools_used,
        actions: (res.pending_actions || []).map((act) => ({
          ...act,
          status: "pending",
        })),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "Failed to reach LOOMOS AI Copilot.";
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          content: errMsg,
          isError: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleActionDecision = async (
    msgId: string,
    actionToken: string,
    decision: "confirm" | "cancel"
  ) => {
    if (decision === "cancel") {
      setMessages((prev) =>
        prev.map((m) =>
          m.id !== msgId
            ? m
            : {
                ...m,
                actions: m.actions?.map((a) =>
                  a.action_token === actionToken ? { ...a, status: "cancelled" } : a
                ),
              }
        )
      );
      return;
    }

    setMessages((prev) =>
      prev.map((m) =>
        m.id !== msgId
          ? m
          : {
              ...m,
              actions: m.actions?.map((a) =>
                a.action_token === actionToken ? { ...a, status: "executing" } : a
              ),
            }
      )
    );

    try {
      const res = await apiRequest<ExecuteAiActionResponse>("/assistant/execute", {
        method: "POST",
        body: JSON.stringify({ action_token: actionToken }),
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id !== msgId
            ? m
            : {
                ...m,
                actions: m.actions?.map((a) =>
                  a.action_token === actionToken
                    ? { ...a, status: "executed", feedback: res.summary }
                    : a
                ),
              }
        )
      );
      window.dispatchEvent(new Event("loomos:data-updated"));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Action failed.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id !== msgId
            ? m
            : {
                ...m,
                actions: m.actions?.map((a) =>
                  a.action_token === actionToken ? { ...a, status: "error", feedback: msg } : a
                ),
              }
        )
      );
    }
  };

  return (
    <>
      {/* Private Floating Launcher Button (only visible for authorized private AI account) */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-30 no-print inline-flex items-center gap-2 px-4 py-3 rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-xl border border-amber-400/50 transition active:scale-95 cursor-pointer"
          aria-label="Open LOOMOS AI Copilot"
        >
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold tracking-wide">
            {tr("LOOMOS AI", "லூமோஸ் AI")}
          </span>
        </button>
      )}

      {/* Slide-Over Copilot Drawer */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end no-print">
          {/* Backdrop */}
          <div
            className="hidden sm:block fixed inset-0 bg-slate-950/40 backdrop-blur-[1px]"
            onClick={() => setOpen(false)}
          />

          <section
            aria-label="LOOMOS AI Copilot"
            className="relative z-10 w-full sm:w-[440px] h-full bg-slate-50 flex flex-col shadow-2xl border-l border-slate-200"
          >
            {/* Header */}
            <header className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between gap-2 shrink-0">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-400/40 flex items-center justify-center shrink-0">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                </div>
                <div className="min-w-0">
                  <div className="font-bold text-sm truncate flex items-center gap-1.5">
                    {tr("LOOMOS AI Copilot", "லூமோஸ் AI உதவியாளர்")}
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">
                    {tr("Private Owner Mode · Live Shed Control", "தனிப்பட்ட உரிமையாளர் · நேரடி கட்டுப்பாடு")}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {/* Fast / Deep Toggle */}
                <div className="flex items-center bg-slate-800 rounded-lg p-0.5 border border-slate-700 text-[11px] font-semibold">
                  <button
                    type="button"
                    onClick={() => setMode("fast")}
                    className={`px-2 py-1 rounded-md inline-flex items-center gap-1 transition cursor-pointer ${
                      mode === "fast" ? "bg-amber-500 text-slate-950" : "text-slate-300 hover:text-white"
                    }`}
                    title="Fast Gemini Flash (~1s)"
                  >
                    <Zap className="w-3 h-3" />
                    {tr("Fast", "வேகம்")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("deep")}
                    className={`px-2 py-1 rounded-md transition cursor-pointer ${
                      mode === "deep" ? "bg-amber-500 text-slate-950" : "text-slate-300 hover:text-white"
                    }`}
                    title="Deep reasoning Gemini model"
                  >
                    {tr("Deep", "ஆழம்")}
                  </button>
                </div>

                {messages.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setMessages([])}
                    className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white cursor-pointer"
                    title={tr("New chat", "புதிய உரையாடல்")}
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="p-1.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white cursor-pointer"
                  aria-label="Close Copilot"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </header>

            {/* Message Feed */}
            <div className="flex-1 overflow-y-auto px-3.5 py-4 space-y-3.5">
              {messages.length === 0 && (
                <div className="space-y-4 py-2">
                  <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs space-y-2">
                    <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      {tr("24/7 Live Shed Copilot Ready", "24/7 நேரடி ஆலை AI தயார்")}
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {tr(
                        "Ask anything in English, Tanglish, or Tamil — check metres, wages, EB bills, beam ETAs, or snap a photo of a delivery challan / TNPDCL bill / cloth defect. Every write action shows a Confirm card first.",
                        "தமிழ், Tanglish அல்லது ஆங்கிலத்தில் எதையும் கேளுங்கள் — மீட்டர், கூலி, EB பில், பீம் ETA பார்க்கலாம் அல்லது பில்/துணி புகைப்படம் அனுப்பி பதிவு செய்யலாம்."
                      )}
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-1">
                      {tr("Quick Actions", "விரைவு கட்டளைகள்")}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {quickPrompts.map((q) => (
                        <button
                          key={q}
                          type="button"
                          onClick={() => void sendMessage(q)}
                          className="text-left text-xs font-medium px-3 py-2 rounded-xl bg-white border border-slate-200 hover:border-amber-400 hover:bg-amber-50/50 text-slate-700 transition cursor-pointer shadow-2xs"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 shadow-2xs ${
                      m.role === "user"
                        ? "bg-slate-900 text-white rounded-br-sm"
                        : m.isError
                        ? "bg-rose-50 border border-rose-200 text-rose-800 rounded-bl-sm"
                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-sm"
                    }`}
                  >
                    {m.imagePreviewUrl && (
                      <img
                        src={m.imagePreviewUrl}
                        alt="Attached"
                        className="mb-2 max-h-44 rounded-xl object-cover border border-white/20"
                      />
                    )}
                    {m.role === "user" ? (
                      <p className="text-sm whitespace-pre-wrap break-words">{m.content}</p>
                    ) : (
                      renderFormattedText(m.content)
                    )}

                    {m.role === "assistant" && !m.isError && m.modelUsed && (
                      <div className="mt-2 pt-1.5 border-t border-slate-100 flex items-center flex-wrap gap-1.5 text-[10px] text-slate-400">
                        <span className="font-mono">{m.modelUsed}</span>
                        {m.toolsUsed && m.toolsUsed.length > 0 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                            <Wrench className="w-2.5 h-2.5" />
                            {m.toolsUsed.length} {tr("live tool", "கருவி")}
                            {m.toolsUsed.length > 1 && lang === "en" ? "s" : ""}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Safe Confirm / Cancel Preview Cards */}
                  {m.actions && m.actions.length > 0 && (
                    <div className="w-full max-w-[95%] mt-2 space-y-2">
                      {m.actions.map((act) => (
                        <div
                          key={act.action_token}
                          className={`rounded-2xl border p-3.5 shadow-xs space-y-2 ${
                            act.status === "executed"
                              ? "bg-emerald-50 border-emerald-300"
                              : act.status === "cancelled"
                              ? "bg-slate-100 border-slate-200 opacity-75"
                              : act.status === "error"
                              ? "bg-rose-50 border-rose-300"
                              : "bg-amber-50/90 border-amber-300"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="text-xs font-bold text-slate-900">{act.title}</div>
                              <div className="text-xs text-slate-700 mt-0.5">{act.summary}</div>
                            </div>
                            {act.status === "executed" && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full shrink-0">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {tr("Applied", "சேமிக்கப்பட்டது")}
                              </span>
                            )}
                            {act.status === "cancelled" && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 bg-slate-200 px-2 py-0.5 rounded-full shrink-0">
                                <XCircle className="w-3.5 h-3.5" />
                                {tr("Cancelled", "ரத்து")}
                              </span>
                            )}
                          </div>

                          <ul className="text-xs text-slate-700 space-y-0.5 pl-1">
                            {act.details.map((d, i) => (
                              <li key={i} className="leading-snug">
                                {d}
                              </li>
                            ))}
                          </ul>

                          {act.status === "error" && act.feedback && (
                            <p className="text-xs text-rose-700 font-medium">{act.feedback}</p>
                          )}

                          {act.status === "executed" && (
                            <div className="flex items-center justify-between pt-1">
                              <span className="text-[11px] text-emerald-700 font-medium">
                                {tr("Saved with Audit Log ✓", "மாற்றப் பதிவில் சேமிக்கப்பட்டது ✓")}
                              </span>
                              <button
                                type="button"
                                onClick={() => window.location.reload()}
                                className="text-[11px] font-semibold text-emerald-800 underline cursor-pointer"
                              >
                                {tr("Refresh screen", "பக்கத்தை புதுப்பி")}
                              </button>
                            </div>
                          )}

                          {(act.status === "pending" || act.status === "executing") && (
                            <div className="flex items-center gap-2 pt-1">
                              <button
                                type="button"
                                disabled={act.status === "executing"}
                                onClick={() => void handleActionDecision(m.id, act.action_token, "confirm")}
                                className="flex-1 py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-bold inline-flex items-center justify-center gap-1.5 cursor-pointer"
                              >
                                {act.status === "executing" ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                )}
                                {tr("Confirm & Apply", "உறுதி செய்து சேமி")}
                              </button>
                              <button
                                type="button"
                                disabled={act.status === "executing"}
                                onClick={() => void handleActionDecision(m.id, act.action_token, "cancel")}
                                className="py-2 px-3 rounded-xl bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold cursor-pointer"
                              >
                                {tr("Cancel", "ரத்து")}
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {sending && (
                <div className="flex items-start">
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-3.5 py-2.5 flex items-center gap-2 text-xs text-slate-500 shadow-2xs">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
                    {tr("Checking live LOOMOS data...", "நேரடி தரவை சரிபார்க்கிறது...")}
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            {/* Attachment Preview Bar */}
            {attachedPreview && attachedFile && (
              <div className="px-3.5 py-2 bg-amber-50 border-t border-amber-200 flex items-center justify-between gap-2 shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                  <img
                    src={attachedPreview}
                    alt="Attachment preview"
                    className="w-10 h-10 rounded-lg object-cover border border-amber-300 shrink-0"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-slate-800 truncate">{attachedFile.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {(attachedFile.size / 1024).toFixed(0)} KB · {tr("Ready to scan", "ஸ்கேன் செய்ய தயார்")}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={clearAttachment}
                  className="p-1 rounded-lg hover:bg-amber-200/70 text-slate-600 cursor-pointer"
                  aria-label="Remove attachment"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Composer Footer */}
            <footer className="bg-white border-t border-slate-200 p-3 shrink-0">
              {/* Hidden file pickers: Camera + Gallery */}
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => handleFilePick(e.target.files?.[0] ?? null)}
              />
              <input
                ref={galleryInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleFilePick(e.target.files?.[0] ?? null)}
              />

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendMessage();
                }}
                className="flex items-end gap-1.5"
              >
                <button
                  type="button"
                  onClick={() => cameraInputRef.current?.click()}
                  disabled={sending}
                  className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 shrink-0 cursor-pointer"
                  title={tr("Take photo (EB bill / challan / cloth)", "கேமரா புகைப்படம்")}
                >
                  <Camera className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => galleryInputRef.current?.click()}
                  disabled={sending}
                  className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 shrink-0 cursor-pointer"
                  title={tr("Attach photo from gallery", "கேலரியில் இருந்து தேர்வு")}
                >
                  <ImagePlus className="w-4 h-4" />
                </button>

                <textarea
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder={tr("Ask anything in English, Tanglish, or தமிழ்...", "தமிழ் / English-ல் கேளுங்கள்...")}
                  className="flex-1 resize-none rounded-xl border border-slate-300 focus:border-amber-500 focus:outline-none px-3 py-2 text-sm max-h-28 bg-slate-50"
                />

                <button
                  type="submit"
                  disabled={sending || (!input.trim() && !attachedFile)}
                  className="p-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-40 text-slate-950 font-bold shrink-0 cursor-pointer transition"
                  aria-label="Send message"
                >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </form>
            </footer>
          </section>
        </div>
      )}
    </>
  );
}

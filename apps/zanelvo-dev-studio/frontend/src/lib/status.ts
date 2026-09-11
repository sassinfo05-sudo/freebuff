// Single source of truth for "what color does this status get" — previously duplicated ad hoc
// across DevStudioApp (task dots), TaskView (plan/test badges), and SettingsPanel (test badges).
export type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

const TONE_BY_STATUS: Record<string, Tone> = {
  // Task / plan item status
  completed: "success",
  verified: "success",
  ready_for_approval: "brand",
  in_progress: "info",
  running: "info",
  planning: "info",
  analyzing: "info",
  implementing: "info",
  reviewing: "info",
  testing: "info",
  committing: "info",
  pending: "neutral",
  queued: "neutral",
  blocked: "warning",
  cancelled: "neutral",
  failed: "danger",
  error: "danger",

  // Test runs / provider test button
  passed: "success",
  ok: "success",
  not_configured: "warning",
  not_implemented: "neutral",

  // GitHub / capability checks
  available: "success",
  unavailable: "warning",
  configured: "success",
};

export function statusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return TONE_BY_STATUS[status.toLowerCase()] ?? "neutral";
}

export function statusDotClass(status: string | null | undefined): string {
  const tone = statusTone(status);
  const map: Record<Tone, string> = {
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    danger: "bg-red-400",
    info: "bg-sky-400",
    brand: "bg-indigo-400",
    neutral: "bg-white/40",
  };
  return map[tone];
}

export function formatStatusLabel(status: string | null | undefined): string {
  if (!status) return "";
  return status.replace(/_/g, " ").toLowerCase();
}

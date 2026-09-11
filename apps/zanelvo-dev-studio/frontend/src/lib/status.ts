// Single source of truth for "what color does this status get" — previously duplicated ad hoc
// across DevStudioApp (task dots), TaskView (plan/test badges), and SettingsPanel (test badges).
export type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

const TONE_BY_STATUS: Record<string, Tone> = {
  // Task status (backend TaskStatus literal, lowercased) — every value must appear here so an
  // "active" task (any state between CREATED and COMPLETED) reliably gets the "info" tone the
  // pulsing dot below keys off of; a missing entry silently falling back to neutral looked done
  // when it wasn't.
  created: "neutral",
  understanding: "info",
  analyzing_repository: "info",
  planning: "info",
  ready: "brand",
  implementing: "info",
  testing: "info",
  debugging: "info",
  reviewing: "info",
  final_verification: "info",
  ready_for_approval: "brand",
  committing: "info",
  pushing: "info",
  completed: "success",
  blocked: "warning",
  failed: "danger",
  cancelled: "neutral",

  // Plan item status
  verified: "success",
  running: "info",
  pending: "neutral",
  skipped: "neutral",

  // Test runs / provider test button
  passed: "success",
  ok: "success",
  not_configured: "warning",
  not_implemented: "neutral",
  error: "danger",

  // GitHub / capability checks
  available: "success",
  unavailable: "warning",
  configured: "success",
};

// Statuses where an agent is genuinely doing work right now — drives the pulsing sidebar dot.
const ACTIVE_STATUSES = new Set([
  "understanding", "analyzing_repository", "planning", "implementing", "testing", "debugging",
  "reviewing", "final_verification", "committing", "pushing", "running",
]);

export function statusTone(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return TONE_BY_STATUS[status.toLowerCase()] ?? "neutral";
}

export function isActiveStatus(status: string | null | undefined): boolean {
  return !!status && ACTIVE_STATUSES.has(status.toLowerCase());
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

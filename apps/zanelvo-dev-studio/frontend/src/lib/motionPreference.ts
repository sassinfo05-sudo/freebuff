const KEY = "zanelvo_reduce_motion";

export function getReduceMotion(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false; // private browsing / storage blocked — default to full motion
  }
}

export function setReduceMotion(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* storage blocked — the toggle still applies for this page load, just won't persist */
  }
  document.documentElement.classList.toggle("reduce-motion", on);
}

export function applyStoredMotionPreference(): void {
  document.documentElement.classList.toggle("reduce-motion", getReduceMotion());
}

// The user's own AI provider key, when they have chosen to supply one.
//
// GramCare runs on free AI tiers with a daily cap. Once that cap is spent,
// every AI feature returns a placeholder answer for the rest of the day.
// Rather than show a dead assistant, the apps offer to use a key of the
// user's own — and someone who has one is then never blocked by the shared
// quota again.
//
// It is a credential, so it stays in this browser and is attached only to
// the AI requests this user makes. It is never sent to a GramCare server as
// anything but that per-request field, and never stored server-side.

const STORAGE_KEY = "gramcare_user_ai_key";

export function getUserAiKey(): string | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value && value.trim() ? value.trim() : null;
  } catch {
    // Storage is unavailable in a private window; behave as if no key was
    // ever supplied rather than breaking the page.
    return null;
  }
}

export function setUserAiKey(value: string): void {
  const trimmed = value.trim();
  if (!trimmed) return;
  try {
    localStorage.setItem(STORAGE_KEY, trimmed);
  } catch {
    // Not persisting is survivable — the caller still holds it for this
    // request, so the retry that follows will work.
  }
}

export function clearUserAiKey(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}

export function hasUserAiKey(): boolean {
  return getUserAiKey() !== null;
}

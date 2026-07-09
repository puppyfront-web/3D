/**
 * Token + user storage helpers for JWT auth.
 *
 * The access token lives in localStorage so it survives reloads and can be
 * injected into every API call (see lib/api.ts / lib/chat-api.ts). These
 * helpers are the single source of truth for reading/writing it — call sites
 * should never touch localStorage directly.
 *
 * NOTE: localStorage is browser-only; every accessor guards on
 * `typeof window` so these are safe to import from server components / SSR.
 */

const TOKEN_KEY = "access_token";
const USER_KEY = "auth_user";

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function setStoredUser(user: { name?: string; email?: string }): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): { name?: string; email?: string } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Redirect to /login if not authenticated. Returns true if the caller should
 * abort (i.e. redirecting). Used by protected page layouts.
 */
export function requireAuth(): boolean {
  if (!isAuthenticated()) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    return true; // abort
  }
  return false;
}

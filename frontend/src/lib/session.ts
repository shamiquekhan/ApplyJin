/** Session token storage + auth-state helpers. */

const TOKEN_KEY = "applyjin_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* private mode — session dies on reload */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

/** Authorization header value, or null when signed out. */
export function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchMe(): Promise<{
  auth_enabled: boolean;
  user: { id: number; email: string; name: string; picture: string } | null;
}> {
  const { API_BASE } = await import("./apiBase");
  const r = await fetch(`${API_BASE}/api/auth/me`, { headers: authHeader() });
  if (!r.ok) throw new Error("Session check failed");
  return r.json();
}

export function logout(onDone?: () => void): void {
  clearToken();
  onDone?.();
}

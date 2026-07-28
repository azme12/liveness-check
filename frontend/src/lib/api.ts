const API_BASE =
  process.env.NEXT_PUBLIC_API_URL !== undefined && process.env.NEXT_PUBLIC_API_URL !== ""
    ? process.env.NEXT_PUBLIC_API_URL
    : typeof window !== "undefined"
      ? ""
      : "http://127.0.0.1:8100";

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("trustanova_token");
}

export function getStoredEnvironment(): "test" | "live" {
  if (typeof window === "undefined") return "test";
  const v = localStorage.getItem("trustanova_env");
  const liveOk = localStorage.getItem("trustanova_live_enabled") === "1";
  if (v === "live" && liveOk) return "live";
  return "test";
}

/** Append ?environment= for dashboard data APIs. */
export function withEnvironment(path: string, env?: "test" | "live"): string {
  const environment = env || getStoredEnvironment();
  if (path.includes("environment=")) return path;
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}environment=${environment}`;
}

export function setSession(token: string, user: unknown) {
  localStorage.setItem("trustanova_token", token);
  localStorage.setItem("trustanova_user", JSON.stringify(user));
  try {
    sessionStorage.removeItem("trustanova_me_cache");
  } catch {
    /* ignore */
  }
}

export function clearSession() {
  localStorage.removeItem("trustanova_token");
  localStorage.removeItem("trustanova_user");
  try {
    sessionStorage.removeItem("trustanova_me_cache");
  } catch {
    /* ignore */
  }
}

export function getStoredUser<T = Record<string, unknown>>(): T | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("trustanova_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function api<T>(
  path: string,
  options: RequestInit & { auth?: boolean; env?: boolean | "test" | "live" } = {},
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (options.auth !== false) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  let finalPath = path;
  const shouldScope =
    options.env !== false &&
    path.startsWith("/api/") &&
    !path.startsWith("/api/auth/") &&
    (options.env === true ||
      options.env === "test" ||
      options.env === "live" ||
      path.startsWith("/api/clients") ||
      path.startsWith("/api/sessions") ||
      path.startsWith("/api/checks") ||
      path.startsWith("/api/workflows") ||
      path.startsWith("/api/overview"));
  if (shouldScope) {
    const env = options.env === "test" || options.env === "live" ? options.env : undefined;
    finalPath = withEnvironment(path, env);
  }

  const res = await fetch(`${API_BASE}${finalPath}`, { ...options, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    clearSession();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  if (!res.ok) {
    let detail = "Request failed";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const PRODUCTION_API = "https://liveness-check-ez3a.onrender.com";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Resolve backend URL in browser when Vercel env var was missing at build time. */
export function resolveApiBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host.endsWith(".vercel.app") || host === "trustanova.vercel.app") {
      return PRODUCTION_API;
    }
    return "";
  }
  return (process.env.BACKEND_URL || "http://127.0.0.1:8100").replace(/\/$/, "");
}

export function networkErrorMessage(err: unknown): string {
  if (err instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(err.message)) {
    return "Cannot reach the API server. The backend may be waking up — wait 30 seconds and try again.";
  }
  if (err instanceof Error) return err.message;
  return "Request failed";
}

/** Retry on network errors and 502/503/504 (Render cold start). */
export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  opts?: { retries?: number; delayMs?: number },
): Promise<Response> {
  const retries = opts?.retries ?? 3;
  const delayMs = opts?.delayMs ?? 2500;
  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(input, init);
      if ((res.status === 502 || res.status === 503 || res.status === 504) && attempt < retries) {
        await sleep(delayMs * (attempt + 1));
        continue;
      }
      return res;
    } catch (err) {
      lastError = err;
      if (attempt < retries) {
        await sleep(delayMs * (attempt + 1));
        continue;
      }
    }
  }

  throw lastError instanceof Error ? lastError : new Error(networkErrorMessage(lastError));
}

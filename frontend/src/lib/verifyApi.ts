import { API_BASE } from "@/lib/api";
import { fetchWithRetry, resolveApiBase } from "@/lib/fetchRetry";

/** Absolute backend URL for public hosted verify calls. */
export function verifyUrl(path: string): string {
  const base = API_BASE || resolveApiBase() || "";
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export { fetchWithRetry };

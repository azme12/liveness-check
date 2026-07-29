import { API_BASE } from "@/lib/api";

/** Absolute backend URL for public hosted verify calls. */
export function verifyUrl(path: string): string {
  const base = API_BASE || "";
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

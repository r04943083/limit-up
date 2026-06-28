// Typed client for the LU local API. Calls go through Next's /api rewrite to FastAPI.
const BASE = "/api";

export type Health = {
  status: string;
  version: string;
  db: string;
  llm_provider: string;
  markets: string[];
};

export async function getHealth(): Promise<Health> {
  const r = await fetch(`${BASE}/health`, { cache: "no-store" });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

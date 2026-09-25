export type InvestigationStatus = "queued" | "running" | "completed" | "failed";

export interface DatabaseStatus {
  connected: boolean;
  version: string | null;
  error: string | null;
}

export interface ActivityEvent {
  sequence: number;
  kind: string;
  summary: string;
  tool_name: string | null;
  result_preview: Record<string, unknown> | null;
  created_at: string;
}

export interface InvestigationReport {
  problem: string;
  evidence: string[];
  root_cause_hypothesis: string;
  recommended_change: string;
  before_after_evidence: string[];
  risks: string[];
  confidence: number;
  sql_recommendation: string | null;
}

export interface Investigation {
  id: string;
  status: InvestigationStatus;
  events: ActivityEvent[];
  report: InvestigationReport | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getDatabaseStatus(): Promise<DatabaseStatus> {
  return request("/api/database/status");
}

export function startInvestigation(problem: string, sql: string): Promise<Investigation> {
  return request("/api/investigate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem, sql: sql.trim() || null })
  });
}

export function getInvestigation(id: string): Promise<Investigation> {
  return request(`/api/investigations/${id}`);
}


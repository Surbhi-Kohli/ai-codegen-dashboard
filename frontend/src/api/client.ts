import type {
  ApiFilters,
  OverviewResponse,
  DeliveryResponse,
  BottlenecksResponse,
  AiImpactResponse,
  AiQualityResponse,
  IssueDetailResponse,
} from "./types";
import {
  MOCK_OVERVIEW,
  MOCK_DELIVERY,
  MOCK_BOTTLENECKS,
  MOCK_AI_IMPACT,
  MOCK_AI_QUALITY,
  getMockIssueDetail,
} from "./mock-data";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function buildParams(filters: ApiFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.repo) params.set("repo", filters.repo);
  if (filters.developer) params.set("developer", filters.developer);
  return params;
}

async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  if (USE_MOCKS) return fallback;

  const res = await fetch(`${API_BASE}${url}`, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return await res.json();
}

export function fetchOverview(filters: ApiFilters): Promise<OverviewResponse> {
  return fetchJson(`/api/overview?${buildParams(filters)}`, MOCK_OVERVIEW);
}

export function fetchDelivery(filters: ApiFilters): Promise<DeliveryResponse> {
  return fetchJson(`/api/delivery?${buildParams(filters)}`, MOCK_DELIVERY);
}

export function fetchBottlenecks(filters: ApiFilters): Promise<BottlenecksResponse> {
  return fetchJson(`/api/bottlenecks?${buildParams(filters)}`, MOCK_BOTTLENECKS);
}

export function fetchAiImpact(filters: ApiFilters): Promise<AiImpactResponse> {
  return fetchJson(`/api/ai-impact?${buildParams(filters)}`, MOCK_AI_IMPACT);
}

export function fetchAiQuality(filters: ApiFilters): Promise<AiQualityResponse> {
  return fetchJson(`/api/ai-quality?${buildParams(filters)}`, MOCK_AI_QUALITY);
}

export function fetchIssueDetail(jiraKey: string): Promise<IssueDetailResponse> {
  return fetchJson(`/api/issues/${jiraKey}`, getMockIssueDetail(jiraKey));
}

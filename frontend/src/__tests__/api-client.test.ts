import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchOverview, fetchIssueDetail } from "../api/client";

describe("API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchOverview returns data from backend when available", async () => {
    const mockData = { kpis: { total_issues: 10, resolved_issues: 5, avg_cycle_time_hours: 24, prs_merged: 3, ai_assisted_pct: 50 } };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    } as Response);

    const result = await fetchOverview({});
    expect(result.kpis.total_issues).toBe(10);
  });

  it("fetchOverview falls back to mock data when backend is down", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network error"));

    const result = await fetchOverview({});
    expect(result.kpis).toBeDefined();
    expect(result.kpis.total_issues).toBeGreaterThan(0);
  });

  it("fetchIssueDetail falls back to mock data for known keys", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Network error"));

    const result = await fetchIssueDetail("ZTAEX-2358");
    expect(result.issue.jira_key).toBe("ZTAEX-2358");
  });
});

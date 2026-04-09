import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import OverviewPage from "../pages/OverviewPage";

vi.spyOn(globalThis, "fetch").mockResolvedValue({
  ok: true,
  json: async () => ({
    kpis: {
      total_issues: 12,
      resolved_issues: 8,
      avg_cycle_time_hours: 45.3,
      prs_merged: 6,
      ai_assisted_pct: 67.5,
    },
  }),
} as Response);

describe("OverviewPage", () => {
  it("renders KPI cards from API data", async () => {
    render(
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("45.3h")).toBeDefined();
    });
    expect(screen.getByText("67.5%")).toBeDefined();
    expect(screen.getByText("6")).toBeDefined();
  });
});

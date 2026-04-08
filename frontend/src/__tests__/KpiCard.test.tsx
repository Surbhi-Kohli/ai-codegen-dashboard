import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import KpiCard from "../components/KpiCard";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Cycle Time" value="24.5h" />);
    expect(screen.getByText("Cycle Time")).toBeDefined();
    expect(screen.getByText("24.5h")).toBeDefined();
  });

  it("renders subtitle when provided", () => {
    render(<KpiCard label="AI %" value="42%" subtitle="of merged lines" />);
    expect(screen.getByText("of merged lines")).toBeDefined();
  });
});

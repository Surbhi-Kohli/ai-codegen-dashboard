import { useOutletContext } from "react-router-dom";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchAiQuality } from "../api/client";
import type { ApiFilters } from "../api/types";

export default function AiQualityPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const { data, loading, error } = useApi(() => fetchAiQuality(filters), [filters]);

  if (loading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;

  const kpis = data!.kpis;
  const flags = data!.oversight_flags;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">AI Quality & Oversight</h2>
      <p className="text-sm text-gray-400 mb-6">
        Is AI-generated code meeting our engineering standards?
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-8">
        <KpiCard
          label="AI Defect Rate"
          value={`${kpis.ai_defect_rate}%`}
          tooltip={"(AI PRs linked to Bug issues / Total AI PRs) × 100%\n\nA PR is defect-linked when its Jira issue type is \"Bug\". Tracks whether AI code produces bugs at a higher rate than human code."}
        />
        <KpiCard
          label="AI Revert Rate"
          value={`${kpis.ai_revert_rate}%`}
          tooltip={"(Reverted AI PRs / Total AI PRs) × 100%\n\nDetected two ways:\n1. Commit message contains \"revert\" + PR number\n2. ≥50% of AI-attributed lines removed within 7 days (line-level diff analysis)"}
        />
        <KpiCard
          label="AI Lines Removed"
          value={`${kpis.avg_ai_lines_removed_ratio}%`}
          subtitle="avg lines reverted"
          tooltip={"Avg % of AI-attributed lines deleted in follow-up commits within 7 days of merge.\n\nUses git diff to check if AI line ranges were actually removed — not just commit message heuristics."}
        />
        <KpiCard
          label="Unmodified AI Ratio"
          value={kpis.avg_unmodified_ratio != null ? `${kpis.avg_unmodified_ratio}%` : "—"}
          subtitle="accepted as-is"
          tooltip={"(AI lines committed as-is / Total AI lines) × 100%\n\nMeasures how much AI code is accepted without human edits. High ratio may indicate insufficient review. Requires git-ai CLI stats."}
        />
        <KpiCard
          label="Blind Accept Rate"
          value={`${kpis.blind_acceptance_rate}%`}
          subtitle="AI reviews dismissed fast"
          tooltip={"(Bot review comments resolved in <2 min / Total bot review threads) × 100%\n\nTracks how often AI-generated review comments are dismissed without reading. Fast resolution suggests the reviewer didn't engage."}
        />
        <KpiCard
          label="No Tests"
          value={`${kpis.prs_without_tests_pct}%`}
          subtitle="AI PRs without tests"
          tooltip={"(AI PRs without test files / Total AI PRs) × 100%\n\nFlags PRs containing AI code but no files in test/, tests/, spec/, or similar directories. AI code without tests is higher risk."}
        />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          Oversight Flags
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          PRs with &gt;80% AI code AND no human edits AND no new tests. Never flagged on a single
          metric alone.
        </p>

        {flags.length === 0 ? (
          <p className="text-gray-500 text-sm">No flagged PRs — looking good.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-800">
                  <th className="py-2 pr-4">PR</th>
                  <th className="py-2 pr-4">Author</th>
                  <th className="py-2 pr-4">AI %</th>
                  <th className="py-2 pr-4">Tests</th>
                  <th className="py-2 pr-4">Unmodified</th>
                  <th className="py-2 pr-4">Blind Accepts</th>
                  <th className="py-2 pr-4">Reverted</th>
                  <th className="py-2 pr-4">Lines Removed</th>
                  <th className="py-2">Defect</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.pr_number} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 pr-4 font-mono text-brand-500">#{f.pr_number}</td>
                    <td className="py-2 pr-4">{f.author}</td>
                    <td className="py-2 pr-4">{f.ai_pct}%</td>
                    <td className="py-2 pr-4">
                      <span className={f.has_tests ? "text-green-400" : "text-red-400"}>
                        {f.has_tests ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="py-2 pr-4">{f.unmodified_ratio ?? "—"}%</td>
                    <td className="py-2 pr-4">{f.blind_accepts}</td>
                    <td className="py-2 pr-4">
                      <span className={f.reverted ? "text-red-400" : "text-gray-500"}>
                        {f.reverted ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      <span className={f.ai_lines_removed_ratio && f.ai_lines_removed_ratio >= 50 ? "text-red-400" : "text-gray-400"}>
                        {f.ai_lines_removed_ratio != null ? `${Math.round(f.ai_lines_removed_ratio * 100)}%` : "—"}
                      </span>
                    </td>
                    <td className="py-2">
                      <span className={f.defect_linked ? "text-red-400" : "text-gray-500"}>
                        {f.defect_linked ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

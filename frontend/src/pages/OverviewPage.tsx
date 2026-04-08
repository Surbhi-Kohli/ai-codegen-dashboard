import { useOutletContext } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchOverview, fetchDelivery } from "../api/client";
import type { ApiFilters } from "../api/types";

export default function OverviewPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const overview = useApi(() => fetchOverview(filters), [filters]);
  const delivery = useApi(() => fetchDelivery(filters), [filters]);

  if (overview.loading) return <p className="text-gray-400">Loading...</p>;
  if (overview.error) return <p className="text-red-400">Error: {overview.error}</p>;

  const kpis = overview.data!.kpis;
  const cycle = delivery.data?.cycle_breakdown;

  const timeDistribution = cycle
    ? [
        { name: "Coding", hours: cycle.avg_coding_hours ?? 0, color: "#0a84ff" },
        { name: "Review", hours: cycle.avg_review_hours ?? 0, color: "#30d158" },
        { name: "Waiting", hours: cycle.avg_waiting_hours ?? 0, color: "#ff9f0a" },
      ]
    : [];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">Overview</h2>
      <p className="text-sm text-gray-400 mb-6">Executive snapshot of team performance</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Avg Cycle Time"
          value={kpis.avg_cycle_time_hours != null ? `${kpis.avg_cycle_time_hours}h` : "—"}
        />
        <KpiCard label="AI Assisted" value={`${kpis.ai_assisted_pct}%`} subtitle="of issues" />
        <KpiCard label="PRs Merged" value={String(kpis.prs_merged)} />
        <KpiCard
          label="Issues Resolved"
          value={`${kpis.resolved_issues} / ${kpis.total_issues}`}
          subtitle="resolved / total"
        />
      </div>

      {timeDistribution.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">
            Time Distribution (avg hours)
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={timeDistribution} layout="vertical">
              <XAxis type="number" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis
                dataKey="name"
                type="category"
                stroke="#636366"
                tick={{ fill: "#86868b", fontSize: 12 }}
                width={70}
              />
              <Tooltip
                contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }}
                labelStyle={{ color: "#f5f5f7" }}
              />
              <Bar dataKey="hours" radius={[0, 4, 4, 0]}>
                {timeDistribution.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

import { useOutletContext } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchDelivery } from "../api/client";
import type { ApiFilters } from "../api/types";

export default function DeliveryPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const { data, loading, error } = useApi(() => fetchDelivery(filters), [filters]);

  if (loading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;

  const cycle = data!.cycle_breakdown;
  const totalHours = cycle.avg_total_hours ?? 0;

  const breakdownData = [
    { name: "Coding", value: cycle.avg_coding_hours ?? 0, color: "#0a84ff" },
    { name: "Review", value: cycle.avg_review_hours ?? 0, color: "#30d158" },
    { name: "Waiting", value: cycle.avg_waiting_hours ?? 0, color: "#ff9f0a" },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">Delivery</h2>
      <p className="text-sm text-gray-400 mb-6">Are we delivering faster and more reliably?</p>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <KpiCard
          label="Avg Cycle Time"
          value={totalHours ? `${totalHours}h` : "—"}
        />
        <KpiCard
          label="Avg Coding Time"
          value={cycle.avg_coding_hours != null ? `${cycle.avg_coding_hours}h` : "—"}
        />
        <KpiCard label="PRs Merged" value={String(data!.prs_merged)} subtitle="in period" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Cycle Time Breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={breakdownData} layout="vertical">
              <XAxis type="number" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} unit="h" />
              <YAxis dataKey="name" type="category" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} width={70} />
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {breakdownData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Time Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={breakdownData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {breakdownData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

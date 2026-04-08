import { useOutletContext } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchBottlenecks } from "../api/client";
import type { ApiFilters } from "../api/types";

export default function BottlenecksPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const { data, loading, error } = useApi(() => fetchBottlenecks(filters), [filters]);

  if (loading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;

  const dist = data!.stage_distribution;
  const stageData = dist
    ? [
        { name: "Coding", pct: dist.coding_pct, color: "#0a84ff" },
        { name: "Review", pct: dist.review_pct, color: "#30d158" },
        { name: "Waiting", pct: dist.waiting_pct, color: "#ff9f0a" },
      ]
    : [];

  const aiWaitMin = data!.avg_time_waiting_for_ai_secs
    ? (data!.avg_time_waiting_for_ai_secs / 60).toFixed(1)
    : null;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">Bottlenecks</h2>
      <p className="text-sm text-gray-400 mb-6">Where is time being spent and where is work getting stuck?</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Review Queue" value={String(data!.review_queue_depth)} subtitle="PRs awaiting review" />
        <KpiCard
          label="Avg Review Rounds"
          value={data!.avg_review_rounds != null ? String(data!.avg_review_rounds) : "—"}
        />
        <KpiCard
          label="Avg AI Wait Time"
          value={aiWaitMin ? `${aiWaitMin}m` : "—"}
          subtitle="per commit"
        />
        <KpiCard
          label="Waiting %"
          value={dist ? `${dist.waiting_pct}%` : "—"}
          subtitle="of cycle time"
        />
      </div>

      {stageData.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Time-in-Stage Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stageData}>
              <XAxis dataKey="name" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} unit="%" />
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
              <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
                {stageData.map((entry, i) => (
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

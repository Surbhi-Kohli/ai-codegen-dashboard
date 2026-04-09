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
import { fetchAiImpact } from "../api/client";
import type { ApiFilters } from "../api/types";

export default function AiImpactPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const { data, loading, error } = useApi(() => fetchAiImpact(filters), [filters]);

  if (loading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;

  const d = data!;
  const topAgent = d.top_agents.length > 0 ? d.top_agents[0].agent : "—";
  const aiWaitMin = d.avg_time_waiting_for_ai_secs
    ? (d.avg_time_waiting_for_ai_secs / 60).toFixed(1)
    : null;

  const prodComparison = [
    { name: "AI-Assisted", hours: d.productivity_comparison.ai_assisted_avg_hours ?? 0, color: "#0a84ff" },
    { name: "Non-AI", hours: d.productivity_comparison.non_ai_avg_hours ?? 0, color: "#636366" },
  ];

  const acceptedVsEdited = [
    { name: "Accepted as-is", value: d.ai_accepted_vs_edited.accepted, color: "#30d158" },
    { name: "Human-edited", value: d.ai_accepted_vs_edited.human_edited, color: "#ff9f0a" },
  ];

  const toolBreakdown = d.tool_model_breakdown.map((t, i) => ({
    name: `${t.tool}/${t.model}`,
    additions: t.additions,
    color: ["#0a84ff", "#30d158", "#ff9f0a", "#ff453a", "#bf5af2"][i % 5],
  }));

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">AI Impact</h2>
      <p className="text-sm text-gray-400 mb-6">How is AI helping?</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="AI Code Merged"
          value={d.avg_ai_code_pct != null ? `${d.avg_ai_code_pct}%` : "—"}
          subtitle="of total lines"
        />
        <KpiCard label="Top Agent" value={topAgent} />
        <KpiCard
          label="AI Accepted Ratio"
          value={d.ai_accepted_ratio != null ? `${d.ai_accepted_ratio}%` : "—"}
          subtitle="accepted as-is"
        />
        <KpiCard
          label="Avg AI Wait"
          value={aiWaitMin ? `${aiWaitMin}m` : "—"}
          subtitle="per commit"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">
            AI vs Non-AI: Avg Cycle Time
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={prodComparison}>
              <XAxis dataKey="name" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} unit="h" />
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
              <Bar dataKey="hours" radius={[4, 4, 0, 0]}>
                {prodComparison.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">AI Code: Accepted vs Edited</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={acceptedVsEdited}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={70}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {acceptedVsEdited.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {toolBreakdown.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Tool & Model Adoption</h3>
          <ResponsiveContainer width="100%" height={Math.max(150, toolBreakdown.length * 40)}>
            <BarChart data={toolBreakdown} layout="vertical">
              <XAxis type="number" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis dataKey="name" type="category" stroke="#636366" tick={{ fill: "#86868b", fontSize: 11 }} width={200} />
              <Tooltip contentStyle={{ background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 }} />
              <Bar dataKey="additions" radius={[0, 4, 4, 0]}>
                {toolBreakdown.map((entry, i) => (
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

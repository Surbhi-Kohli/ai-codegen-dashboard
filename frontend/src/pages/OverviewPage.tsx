import { useState } from "react";
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
import { fetchOverview, fetchDelivery, fetchBottlenecks, sendWebexOverview } from "../api/client";
import type { ApiFilters } from "../api/types";

const TOOLTIP_STYLE = { background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 };

export default function OverviewPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const overview = useApi(() => fetchOverview(filters), [filters]);
  const delivery = useApi(() => fetchDelivery(filters), [filters]);
  const bottlenecks = useApi(() => fetchBottlenecks(filters), [filters]);

  const [webexStatus, setWebexStatus] = useState<string | null>(null);
  const [webexSending, setWebexSending] = useState(false);

  const handleWebexSend = async () => {
    setWebexSending(true);
    setWebexStatus(null);
    try {
      const result = await sendWebexOverview();
      if (result.status === "sent") {
        setWebexStatus("Team summary sent to Webex");
      } else {
        setWebexStatus(`${result.status}: ${result.reason || result.detail || "unknown"}`);
      }
    } catch (e: any) {
      setWebexStatus(`Error: ${e.message}`);
    }
    setWebexSending(false);
  };

  if (overview.loading) return <p className="text-gray-400">Loading...</p>;
  if (overview.error) return <p className="text-red-400">Error: {overview.error}</p>;

  const kpis = overview.data!.kpis;
  const cycle = delivery.data?.cycle_breakdown;
  const bn = bottlenecks.data;

  const breakdownData = cycle
    ? [
        { name: "Coding", hours: cycle.avg_coding_hours ?? 0, color: "#0a84ff" },
        { name: "Review", hours: cycle.avg_review_hours ?? 0, color: "#30d158" },
        { name: "Waiting", hours: cycle.avg_waiting_hours ?? 0, color: "#ff9f0a" },
      ]
    : [];

  const totalHours = breakdownData.reduce((s, d) => s + d.hours, 0);
  const pieData = totalHours > 0
    ? breakdownData.map((d) => ({ ...d, value: d.hours }))
    : [];

  const aiWaitMin = bn?.avg_time_waiting_for_ai_secs
    ? (bn.avg_time_waiting_for_ai_secs / 60).toFixed(1)
    : null;

  return (
    <div>
      {/* ── Header + Webex ── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold mb-1">Overview</h2>
          <p className="text-sm text-gray-400">
            Executive snapshot of team performance — delivery speed, cycle time, and bottlenecks
          </p>
        </div>
        <button
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors whitespace-nowrap shrink-0 ml-6"
          disabled={webexSending}
          onClick={handleWebexSend}
        >
          {webexSending ? "Sending..." : "Send Summary to Webex"}
        </button>
      </div>

      {webexStatus && (
        <div className={`mb-4 text-sm px-3 py-2 rounded-lg ${
          webexStatus.startsWith("Sent") ? "bg-green-900/30 text-green-400 border border-green-800" : "bg-red-900/30 text-red-400 border border-red-800"
        }`}>
          {webexStatus}
        </div>
      )}

      {/* ── KPI Row 1: Delivery ── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
        <KpiCard
          label="Avg Cycle Time"
          value={kpis.avg_cycle_time_hours != null ? `${kpis.avg_cycle_time_hours}h` : "—"}
        />
        <KpiCard
          label="Avg Coding Time"
          value={cycle?.avg_coding_hours != null ? `${cycle.avg_coding_hours}h` : "—"}
        />
        <KpiCard label="AI Assisted" value={`${kpis.ai_assisted_pct}%`} subtitle="of issues" />
        <KpiCard label="PRs Merged" value={String(kpis.prs_merged)} />
        <KpiCard
          label="Issues Resolved"
          value={`${kpis.resolved_issues} / ${kpis.total_issues}`}
          subtitle="resolved / total"
        />
      </div>

      {/* ── KPI Row 2: Bottlenecks ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Review Queue"
          value={bn ? String(bn.review_queue_depth) : "—"}
          subtitle="PRs awaiting review"
        />
        <KpiCard
          label="Avg Review Rounds"
          value={bn?.avg_review_rounds != null ? String(bn.avg_review_rounds) : "—"}
        />
        <KpiCard
          label="Avg AI Wait"
          value={aiWaitMin ? `${aiWaitMin}m` : "—"}
          subtitle="per commit"
        />
        <KpiCard
          label="Waiting %"
          value={bn?.stage_distribution ? `${bn.stage_distribution.waiting_pct}%` : "—"}
          subtitle="of cycle time"
        />
      </div>

      {/* ── Charts: Cycle Time Breakdown + Time Distribution Pie ── */}
      {breakdownData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Cycle Time Breakdown</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={breakdownData} layout="vertical">
                <XAxis type="number" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} unit="h" />
                <YAxis dataKey="name" type="category" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} width={70} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="hours" radius={[0, 4, 4, 0]}>
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
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

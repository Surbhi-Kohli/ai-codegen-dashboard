import { useParams, Link } from "react-router-dom";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchIssueDetail } from "../api/client";

export default function IssueDetailPage() {
  const { jiraKey } = useParams<{ jiraKey: string }>();
  const { data, loading, error } = useApi(() => fetchIssueDetail(jiraKey!), [jiraKey]);

  if (loading) return <p className="text-gray-400">Loading...</p>;
  if (error) return <p className="text-red-400">Error: {error}</p>;
  if (!data) return null;

  const { issue, transitions, pull_requests, cycle_metrics } = data;

  return (
    <div>
      <Link to="/overview" className="text-brand-500 text-sm hover:underline mb-4 inline-block">
        &larr; Back to Overview
      </Link>

      <h2 className="text-xl font-semibold mb-1">
        {issue.jira_key}: {issue.summary}
      </h2>
      <p className="text-sm text-gray-400 mb-6">
        {issue.type} &middot; {issue.status} &middot; Created{" "}
        {new Date(issue.created_at).toLocaleDateString()}
      </p>

      {cycle_metrics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <KpiCard
            label="Total Cycle Time"
            value={cycle_metrics.total_cycle_time_hours != null ? `${cycle_metrics.total_cycle_time_hours}h` : "—"}
          />
          <KpiCard
            label="Coding"
            value={cycle_metrics.coding_time_hours != null ? `${cycle_metrics.coding_time_hours}h` : "—"}
          />
          <KpiCard
            label="Review"
            value={cycle_metrics.review_time_hours != null ? `${cycle_metrics.review_time_hours}h` : "—"}
          />
          <KpiCard
            label="AI Assisted"
            value={cycle_metrics.is_ai_assisted ? `${cycle_metrics.ai_percentage ?? 0}%` : "No"}
          />
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Status Timeline</h3>
        <div className="space-y-3">
          {transitions.map((t, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="text-gray-500 w-40 shrink-0">
                {new Date(t.at).toLocaleString()}
              </span>
              <span className="text-gray-400">{t.from ?? "—"}</span>
              <span className="text-gray-600">&rarr;</span>
              <span className="text-white font-medium">{t.to}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">
          Linked Pull Requests ({pull_requests.length})
        </h3>
        {pull_requests.length === 0 ? (
          <p className="text-gray-500 text-sm">No linked PRs.</p>
        ) : (
          <div className="space-y-3">
            {pull_requests.map((pr) => (
              <div
                key={pr.number}
                className="flex items-center justify-between text-sm border-b border-gray-800/50 pb-2"
              >
                <div>
                  <span className="font-mono text-brand-500">#{pr.number}</span>{" "}
                  <span className="text-gray-200">{pr.title}</span>
                  <span className="text-gray-500 ml-2">by {pr.author}</span>
                </div>
                <div className="flex items-center gap-4 text-gray-400">
                  <span>AI {pr.ai_percentage}%</span>
                  <span
                    className={
                      pr.state === "merged"
                        ? "text-purple-400"
                        : pr.state === "open"
                        ? "text-green-400"
                        : "text-gray-500"
                    }
                  >
                    {pr.state}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

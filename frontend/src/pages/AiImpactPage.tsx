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
  Treemap,
} from "recharts";
import KpiCard from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { fetchAiImpact } from "../api/client";
import type { ApiFilters } from "../api/types";

const TOOLTIP_STYLE = { background: "#2d2d2f", border: "1px solid #424245", borderRadius: 6 };

function TreemapContent({ x, y, width, height, name, ai_lines }: any) {
  if (width < 40 || height < 24) return null;
  const shortName = name?.split("/").pop() ?? "";
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4} fill="#0a84ff" fillOpacity={0.7} stroke="#1d1d1f" strokeWidth={1} />
      <text x={x + 6} y={y + 16} fill="#e5e5ea" fontSize={11} fontWeight={500}>
        {shortName.length > width / 7 ? shortName.slice(0, Math.floor(width / 7)) + "…" : shortName}
      </text>
      {height > 36 && (
        <text x={x + 6} y={y + 30} fill="#86868b" fontSize={10}>
          {ai_lines} lines
        </text>
      )}
    </g>
  );
}

export default function AiImpactPage() {
  const { filters } = useOutletContext<{ filters: ApiFilters }>();
  const { data, loading, error } = useApi(() => fetchAiImpact(filters), [filters]);
  const [expandedFile, setExpandedFile] = useState<string | null>(null);

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

  const toolBreakdown = (d.tool_model_breakdown ?? []).map((t: any) => ({
    name: `${t.tool}/${t.model}`,
    additions: t.additions,
    accepted: t.accepted,
  }));

  const fileHeatmap = (d.file_heatmap ?? []).map((f: any) => ({
    name: f.file,
    ai_lines: f.ai_lines,
    regions: f.regions,
    model: f.model,
  }));

  const fileRanges: Record<string, any[]> = d.file_ranges ?? {};
  const commitTimeline: any[] = d.commit_timeline ?? [];
  const promptActivity: any[] = d.prompt_activity ?? [];
  const authorContributions: any[] = d.author_contributions ?? [];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1">AI Impact</h2>
      <p className="text-sm text-gray-400 mb-6">How is AI helping?</p>

      {/* ── KPI Row ── */}
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

      {/* ── Row: Cycle Time + Accepted vs Edited ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">
            AI vs Non-AI: Avg Cycle Time
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={prodComparison}>
              <XAxis dataKey="name" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} unit="h" />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
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
              <Tooltip contentStyle={TOOLTIP_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Tool & Model ── */}
      {toolBreakdown.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">Tool & Model: Generated vs Accepted</h3>
          <ResponsiveContainer width="100%" height={Math.max(150, toolBreakdown.length * 50)}>
            <BarChart data={toolBreakdown} layout="vertical">
              <XAxis type="number" stroke="#636366" tick={{ fill: "#86868b", fontSize: 12 }} />
              <YAxis dataKey="name" type="category" stroke="#636366" tick={{ fill: "#86868b", fontSize: 11 }} width={200} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="additions" name="Generated" fill="#0a84ff" radius={[0, 4, 4, 0]} />
              <Bar dataKey="accepted" name="Accepted as-is" fill="#30d158" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-6 mt-3 text-xs text-gray-400">
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[#0a84ff] inline-block" /> Generated</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[#30d158] inline-block" /> Accepted as-is</span>
          </div>
        </div>
      )}

      {/* ── NEW: File-Level AI Heatmap ── */}
      {fileHeatmap.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-1">File-Level AI Heatmap</h3>
          <p className="text-xs text-gray-500 mb-4">Which files have AI-written code and how much. Click a file to see exact line ranges.</p>
          <ResponsiveContainer width="100%" height={Math.max(180, fileHeatmap.length * 22)}>
            <Treemap
              data={fileHeatmap}
              dataKey="ai_lines"
              stroke="#1d1d1f"
              content={<TreemapContent />}
              onClick={(node: any) => setExpandedFile(node?.name === expandedFile ? null : node?.name)}
            />
          </ResponsiveContainer>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <th className="text-left py-2 pr-4">File</th>
                  <th className="text-right py-2 pr-4">AI Lines</th>
                  <th className="text-right py-2 pr-4">Regions</th>
                  <th className="text-left py-2">Model</th>
                </tr>
              </thead>
              <tbody>
                {fileHeatmap.map((f: any) => (
                  <>
                    <tr
                      key={f.name}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => setExpandedFile(f.name === expandedFile ? null : f.name)}
                    >
                      <td className="py-2 pr-4 font-mono text-xs text-blue-400">
                        {expandedFile === f.name ? "▼" : "▶"} {f.name}
                      </td>
                      <td className="text-right py-2 pr-4 text-green-400 font-semibold">{f.ai_lines}</td>
                      <td className="text-right py-2 pr-4 text-gray-400">{f.regions}</td>
                      <td className="py-2 text-gray-400 text-xs">{f.model}</td>
                    </tr>
                    {expandedFile === f.name && fileRanges[f.name] && (
                      <tr key={`${f.name}-detail`}>
                        <td colSpan={4} className="py-0 pb-2">
                          <div className="ml-6 bg-gray-950 border border-gray-800 rounded-md p-3">
                            <div className="text-xs text-gray-500 mb-2 font-semibold">Line Ranges (AI-written)</div>
                            <div className="space-y-1">
                              {fileRanges[f.name].map((r: any, i: number) => (
                                <div key={i} className="flex items-center gap-3 text-xs">
                                  <span className="font-mono text-yellow-400 min-w-[80px]">L{r.start}–L{r.end}</span>
                                  <span className="text-gray-400">{r.lines} lines</span>
                                  <span className="text-gray-600">•</span>
                                  <span className="text-purple-400">{r.model}</span>
                                  <span className="text-gray-600">•</span>
                                  <span className="text-gray-500 font-mono">{r.commit}</span>
                                  {r.prompt_id && (
                                    <>
                                      <span className="text-gray-600">•</span>
                                      <span className="text-cyan-500 font-mono text-[10px]">prompt:{r.prompt_id}</span>
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── NEW: Commit Timeline ── */}
      {commitTimeline.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-1">AI Commit Timeline</h3>
          <p className="text-xs text-gray-500 mb-4">Each commit that contained AI-generated code, with model and line counts.</p>
          <div className="space-y-3">
            {commitTimeline.map((c: any) => (
              <div key={c.sha} className="flex items-start gap-4 border-l-2 border-blue-500/50 pl-4 py-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-blue-400">{c.sha}</span>
                    <span className="text-gray-600 text-xs">
                      {c.committed_at ? new Date(c.committed_at).toLocaleString() : ""}
                    </span>
                  </div>
                  <div className="text-sm text-gray-200 truncate">{c.message}</div>
                  <div className="flex items-center gap-4 mt-1 text-xs">
                    <span className="text-gray-500">by <span className="text-gray-300">{c.author}</span></span>
                    <span className="text-green-400">+{c.ai_additions} AI</span>
                    {c.human_additions > 0 && <span className="text-gray-400">+{c.human_additions} human</span>}
                    <span className="text-purple-400">{c.models?.join(", ")}</span>
                    {c.time_waiting_secs > 0 && (
                      <span className="text-yellow-400">waited {c.time_waiting_secs}s</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <div className="bg-blue-500/20 text-blue-400 text-xs font-semibold px-2 py-0.5 rounded">
                    {c.ai_accepted ?? c.ai_additions} accepted
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── NEW: Prompt Activity ── */}
      {promptActivity.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-1">Prompt Activity</h3>
          <p className="text-xs text-gray-500 mb-4">Each AI prompt session and the files it touched.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <th className="text-left py-2 pr-4">Prompt ID</th>
                  <th className="text-left py-2 pr-4">Author</th>
                  <th className="text-left py-2 pr-4">Agent / Model</th>
                  <th className="text-right py-2 pr-4">Regions</th>
                  <th className="text-right py-2 pr-4">Lines</th>
                  <th className="text-left py-2">Files Touched</th>
                </tr>
              </thead>
              <tbody>
                {promptActivity.map((p: any) => (
                  <tr key={p.prompt_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 pr-4 font-mono text-xs text-cyan-400">{p.prompt_id}</td>
                    <td className="py-2 pr-4 text-gray-300">{p.author}</td>
                    <td className="py-2 pr-4 text-purple-400 text-xs">{p.agent}/{p.model}</td>
                    <td className="text-right py-2 pr-4 text-gray-400">{p.regions}</td>
                    <td className="text-right py-2 pr-4 text-green-400 font-semibold">{p.total_lines}</td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {p.files.map((f: string) => (
                          <span key={f} className="bg-gray-800 text-gray-400 text-[10px] font-mono px-1.5 py-0.5 rounded">
                            {f.split("/").pop()}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── NEW: Author AI Contributions ── */}
      {authorContributions.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-1">Developer AI Contributions</h3>
          <p className="text-xs text-gray-500 mb-4">Who used AI and how much code was generated.</p>
          <div className="space-y-3">
            {authorContributions.map((a: any) => {
              const maxLines = Math.max(...authorContributions.map((x: any) => x.ai_lines), 1);
              const pct = (a.ai_lines / maxLines) * 100;
              return (
                <div key={`${a.author}-${a.agent}`} className="flex items-center gap-4">
                  <div className="w-36 text-sm text-gray-200 truncate">{a.author}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-800 rounded-full h-5 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full flex items-center pl-2"
                          style={{ width: `${Math.max(pct, 8)}%` }}
                        >
                          <span className="text-[10px] font-semibold text-white">{a.ai_lines} lines</span>
                        </div>
                      </div>
                      <span className="text-xs text-gray-500 w-24 text-right">{a.attributions} regions</span>
                    </div>
                  </div>
                  <span className="text-xs text-purple-400 w-16">{a.agent}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

import type {
  OverviewResponse,
  DeliveryResponse,
  BottlenecksResponse,
  AiImpactResponse,
  AiQualityResponse,
  IssueDetailResponse,
} from "./types";

export const MOCK_OVERVIEW: OverviewResponse = {
  kpis: {
    total_issues: 12,
    resolved_issues: 7,
    avg_cycle_time_hours: 142.8,
    prs_merged: 6,
    ai_assisted_pct: 71.4,
  },
};

export const MOCK_DELIVERY: DeliveryResponse = {
  cycle_breakdown: {
    avg_coding_hours: 62.4,
    avg_review_hours: 48.2,
    avg_waiting_hours: 32.2,
    avg_total_hours: 142.8,
  },
  prs_merged: 6,
};

export const MOCK_BOTTLENECKS: BottlenecksResponse = {
  review_queue_depth: 3,
  avg_review_rounds: 1.8,
  stage_distribution: {
    coding_pct: 43.7,
    review_pct: 33.8,
    waiting_pct: 22.5,
  },
  avg_time_waiting_for_ai_secs: 42,
};

export const MOCK_AI_IMPACT: AiImpactResponse = {
  avg_ai_code_pct: 43.7,
  top_agents: [
    { agent: "cursor", count: 18 },
    { agent: "copilot", count: 12 },
    { agent: "claude-code", count: 5 },
  ],
  productivity_comparison: {
    ai_assisted_avg_hours: 120.5,
    non_ai_avg_hours: 188.0,
  },
  ai_accepted_ratio: 72.4,
  ai_accepted_vs_edited: {
    accepted: 648,
    human_edited: 247,
  },
  avg_time_waiting_for_ai_secs: 42,
  tool_model_breakdown: [
    { tool: "cursor", model: "claude-sonnet-4-20250514", additions: 520, accepted: 385 },
    { tool: "copilot", model: "gpt-4o", additions: 280, accepted: 195 },
    { tool: "claude-code", model: "claude-sonnet-4-20250514", additions: 95, accepted: 68 },
  ],
};

export const MOCK_AI_QUALITY: AiQualityResponse = {
  kpis: {
    ai_defect_rate: 8.3,
    ai_revert_rate: 0.0,
    avg_unmodified_ratio: 72.4,
    blind_acceptance_rate: 12.5,
    prs_without_tests_pct: 50.0,
  },
  oversight_flags: [
    {
      pr_number: 48410,
      title: "[ZTAEX-2330] Add Duo Desktop health check endpoint",
      author: "bsharko-cisco",
      ai_pct: 63.7,
      has_tests: false,
      unmodified_ratio: 85.2,
      blind_accepts: 1,
      reverted: false,
      defect_linked: false,
    },
    {
      pr_number: 48440,
      title: "[ZTAEX-2345] Implement session trust quarantine API v2",
      author: "bryduo",
      ai_pct: 55.0,
      has_tests: false,
      unmodified_ratio: 68.9,
      blind_accepts: 0,
      reverted: false,
      defect_linked: true,
    },
  ],
};

export function getMockIssueDetail(jiraKey: string): IssueDetailResponse {
  const issues: Record<string, IssueDetailResponse> = {
    "ZTAEX-2358": {
      issue: {
        jira_key: "ZTAEX-2358",
        type: "Task",
        summary: "Update test CODEOWNERS for adminserv adminapiserv and adminapi-evergreen",
        status: "Done",
        created_at: "2026-03-27T08:48:26-07:00",
        resolved_at: "2026-04-03T09:16:20-07:00",
      },
      transitions: [
        { from: "Backlog", to: "Selected for Development", at: "2026-03-27T09:00:00+00:00" },
        { from: "Selected for Development", to: "In Progress", at: "2026-03-28T08:00:00+00:00" },
        { from: "In Progress", to: "Code Review", at: "2026-03-28T14:00:00+00:00" },
        { from: "Code Review", to: "Done", at: "2026-04-03T09:16:20+00:00" },
      ],
      pull_requests: [
        {
          number: 48450,
          title: "[ZTAEX-2358] Update test CODEOWNERS for adminserv",
          author: "largotte-cisco",
          state: "merged",
          ai_percentage: 41.3,
          opened_at: "2026-03-28T14:00:00+00:00",
          merged_at: "2026-03-31T11:00:00+00:00",
        },
      ],
      cycle_metrics: {
        coding_time_hours: 6.0,
        review_time_hours: 66.8,
        waiting_time_hours: 19.3,
        total_cycle_time_hours: 92.1,
        is_ai_assisted: true,
        ai_percentage: 41.3,
        ai_accepted_ratio: 78.0,
        total_time_waiting_for_ai_secs: 35,
        primary_tool: "cursor",
        review_rounds: 1,
      },
    },
    "ZTAEX-2340": {
      issue: {
        jira_key: "ZTAEX-2340",
        type: "Task",
        summary: "Migrate adminserv webpack config to rspack",
        status: "Done",
        created_at: "2026-03-10T10:00:00-07:00",
        resolved_at: "2026-03-20T14:30:00-07:00",
      },
      transitions: [
        { from: "Backlog", to: "In Progress", at: "2026-03-11T09:00:00+00:00" },
        { from: "In Progress", to: "Code Review", at: "2026-03-14T10:00:00+00:00" },
        { from: "Code Review", to: "Done", at: "2026-03-20T14:30:00+00:00" },
      ],
      pull_requests: [
        {
          number: 48430,
          title: "[ZTAEX-2340] Migrate adminserv webpack to rspack",
          author: "largotte-cisco",
          state: "merged",
          ai_percentage: 53.5,
          opened_at: "2026-03-14T10:00:00+00:00",
          merged_at: "2026-03-19T09:00:00+00:00",
        },
      ],
      cycle_metrics: {
        coding_time_hours: 73.0,
        review_time_hours: 100.5,
        waiting_time_hours: 75.5,
        total_cycle_time_hours: 249.0,
        is_ai_assisted: true,
        ai_percentage: 53.5,
        ai_accepted_ratio: 65.0,
        total_time_waiting_for_ai_secs: 58,
        primary_tool: "cursor",
        review_rounds: 2,
      },
    },
  };

  return (
    issues[jiraKey] ?? {
      issue: {
        jira_key: jiraKey,
        type: "Task",
        summary: `Issue ${jiraKey} (mock)`,
        status: "Unknown",
        created_at: "2026-03-01T00:00:00+00:00",
        resolved_at: null,
      },
      transitions: [],
      pull_requests: [],
      cycle_metrics: null,
    }
  );
}

/** Matches GET /api/overview response */
export interface OverviewResponse {
  kpis: {
    total_issues: number;
    resolved_issues: number;
    avg_cycle_time_hours: number | null;
    prs_merged: number;
    ai_assisted_pct: number;
  };
}

/** Matches GET /api/delivery response */
export interface DeliveryResponse {
  cycle_breakdown: {
    avg_coding_hours: number | null;
    avg_review_hours: number | null;
    avg_waiting_hours: number | null;
    avg_total_hours: number | null;
  };
  prs_merged: number;
}

/** Matches GET /api/bottlenecks response */
export interface BottlenecksResponse {
  review_queue_depth: number;
  avg_review_rounds: number | null;
  stage_distribution: {
    coding_pct: number;
    review_pct: number;
    waiting_pct: number;
  };
  avg_time_waiting_for_ai_secs: number | null;
}

/** Matches GET /api/ai-impact response */
export interface AiImpactResponse {
  avg_ai_code_pct: number | null;
  top_agents: { agent: string; count: number }[];
  productivity_comparison: {
    ai_assisted_avg_hours: number | null;
    non_ai_avg_hours: number | null;
  };
  ai_accepted_ratio: number | null;
  ai_accepted_vs_edited: {
    accepted: number;
    human_edited: number;
  };
  avg_time_waiting_for_ai_secs: number | null;
  tool_model_breakdown: {
    tool: string;
    model: string;
    additions: number;
    accepted: number;
  }[];
}

/** Matches GET /api/ai-quality response */
export interface AiQualityResponse {
  kpis: {
    ai_defect_rate: number;
    ai_revert_rate: number;
    avg_unmodified_ratio: number | null;
    blind_acceptance_rate: number;
    prs_without_tests_pct: number;
  };
  oversight_flags: {
    pr_number: number;
    title: string;
    author: string;
    ai_pct: number;
    has_tests: boolean;
    unmodified_ratio: number;
    blind_accepts: number;
    reverted: boolean;
    defect_linked: boolean;
  }[];
}

/** Matches GET /api/issues/{jira_key} response */
export interface IssueDetailResponse {
  issue: {
    jira_key: string;
    type: string;
    summary: string;
    status: string;
    created_at: string;
    resolved_at: string | null;
  };
  transitions: {
    from: string | null;
    to: string;
    at: string;
  }[];
  pull_requests: {
    number: number;
    title: string;
    author: string;
    state: string;
    ai_percentage: number;
    opened_at: string | null;
    merged_at: string | null;
  }[];
  cycle_metrics: {
    coding_time_hours: number | null;
    review_time_hours: number | null;
    waiting_time_hours: number | null;
    total_cycle_time_hours: number | null;
    is_ai_assisted: boolean;
    ai_percentage: number | null;
    ai_accepted_ratio: number | null;
    total_time_waiting_for_ai_secs: number | null;
    primary_tool: string | null;
    review_rounds: number | null;
  } | null;
}

/** Common filter params for API calls */
export interface ApiFilters {
  start_date?: string;
  end_date?: string;
  repo?: string;
  developer?: string;
  project?: string;
}

/** Board info from /api/boards */
export interface BoardInfo {
  key: string;
  issue_count: number;
}

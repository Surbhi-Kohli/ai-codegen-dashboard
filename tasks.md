Prototype the dashboard UI (React + Tailwind) with mock data
Build the backend ingestion for git-ai, GitHub webhooks, Jira polling
Set up git-ai on a test repo to start collecting real AI attribution data
Scope the hackathon deliverable — which pillar(s) to demo first


Here's the full task breakdown for the backend ingestion system, based on the architecture in your design doc.
## Backend Ingestion — Major Tasks

### Layer 0: Infrastructure & Foundation

| # | Task | Details | Depends On |
|---|------|---------|------------|
| **B12** | **Service scaffold** | Python project setup (FastAPI or Flask), config management (env vars for Jira/GitHub/Webex tokens, DB credentials), Docker setup, webhook secret validation | — |
| **B1** | **Database schema** | Create all tables from the data model: `Issue`, `IssueTransition`, `Sprint`, `TimeLog`, `PullRequest`, `Commit`, `AIAttribution`, `ReviewComment`, `WebexMessage`, `IssueCycleMetrics`, `AIQualityMetrics`, `Developer`, `Repository`. Postgres recommended. | B12 |

### Layer 1: Data Ingestion (4 independent pipelines)

| # | Task | Details | Depends On |
|---|------|---------|------------|
| **B2** | **Jira poller** | Poll every 15-30 min using Jira REST API. Ingest issues (id, type, status, assignee, story points, created_at, resolved_at), status transitions (with timestamps from changelog), sprint data, and time logs. Handle pagination, rate limits, incremental sync (track last poll timestamp). | B1 |
| **B3** | **GitHub webhook receiver** | Register webhooks for `pull_request`, `pull_request_review`, `pull_request_review_comment`, `push` events. Parse and store PR lifecycle (opened, review_requested, approved, merged), review comments (with file_path + line_number), commit metadata. Validate webhook signatures. | B1 |
| **B4** | **git-ai hook receiver** | HTTP endpoint that receives POST from git-ai's post-push hook. Parse Git Notes payload: commit SHA, file_path, line ranges (start/end), agent name, model name, AI line counts. Store in `AIAttribution` table. Backfill endpoint for historical repos. | B1 |
| **B5** | **Webex webhook receiver** | Register webhooks for `messages:created` in the team's review Webex space. Match messages containing PR URLs to PRs. Track thread reply timestamps for response time calculation. | B1 |

### Layer 2: Enrichment Engine (runs after ingestion)

| # | Task | Details | Depends On |
|---|------|---------|------------|
| **B6** | **Issue ↔ PR linker** | Match Jira issue key in branch name (regex: `PROJ-\d+`) or PR body/title. Create foreign key links. Re-run on each new PR or issue update. | B2, B3 |
| **B7** | **Review comment ↔ AI code correlator** | For each review comment, check if its `file_path + line_number` falls within any `AIAttribution` line range for that PR's commits. Tag comment as "on AI code" or "on human code". | B3, B4 |
| **B8** | **IssueCycleMetrics computation** | For each issue, compute: coding_time (first PR created - issue "In Progress"), review_time (PR approved - first review requested), waiting_time (cycle - coding - review), total_cycle_time, is_ai_assisted (any linked PR has AI attribution), ai_percentage (avg across linked PRs), review_rounds, comment densities. Recompute on any relevant event. | B6, B7 |
| **B9** | **AIQualityMetrics computation** | For each merged PR with AI code, compute: unmodified_ai_ratio (compare git-ai snapshot to final diff), ai_review_blind_accepts (threads resolved <2 min), followup_fixes_24h (subsequent commits modifying AI lines), test coverage flags (test files in diff), defect_linked (bug issue linked later), reverted_within_7d (monitor for 7 days post-merge). | B4, B6, B7 |
| **B10** | **Webex-PR linker + Developer identity mapper** | Link Webex messages to PRs via URL detection. Create unified developer identity mapping (GitHub username ↔ Jira account_id ↔ Webex person_id). Manual mapping table with auto-suggest. | B3, B5 |

### Layer 3: Dashboard API

| # | Task | Details | Depends On |
|---|------|---------|------------|
| **B11** | **Read endpoints** | REST API serving pre-computed data for all 5 views. Endpoints: `/api/overview`, `/api/delivery`, `/api/bottlenecks`, `/api/ai-impact`, `/api/ai-quality`. Support filters: date range, granularity, repo, developer. Return JSON for frontend consumption. | B8, B9 |

---

### Recommended build order

```
Phase 1 (Foundation):    B12 → B1
Phase 2 (Ingest):        B2 + B3 + B4 in parallel  (B5 can wait)
Phase 3 (Enrich):        B6 → B7 → B8 + B9 in parallel
Phase 4 (Serve):         B11
Phase 5 (Stretch):       B5 → B10
```

### For hackathon scope

If time is limited, the **minimum viable backend** is:

- **B12** (scaffold) → **B1** (DB) → **B2** (Jira) + **B3** (GitHub) → **B6** (linker) → **B8** (cycle metrics) → **B11** (API)

This gives you Pillars 1 & 2 (delivery speed + bottlenecks) with real data. Pillar 3 & 4 (AI Impact + Quality) require git-ai (**B4**) which adds **B7** and **B9**.


# AI Codegen Dashboard - Design Specification

**Date:** 2026-04-02
**Status:** Draft
**Audience:** Engineering managers (primary), executives (secondary), individual developers (tertiary)
**Scope:** Single team, up to 5 repositories

## 1. Problem Statement

Project managers and engineering leaders need visibility into how AI is being leveraged for code generation across their team. Specifically, they need to answer four questions:

1. **Are we delivering faster and more reliably?**
2. **Where is time being spent and where is work getting stuck?**
3. **How is AI helping?**
4. **Is AI-generated code meeting our engineering standards?**

There is no unified view today. Data lives across Jira (issue tracking, sprints), GitHub (PRs, reviews), git-ai (AI attribution), and Webex (team communication). This dashboard unifies those sources into actionable metrics with flexible time-range filtering and drill-down from team to developer to individual issue.

## 2. Data Sources

| Source | Ingestion Method | Data Provided |
|--------|-----------------|---------------|
| **git-ai** | Git post-push hook POSTs to backend API | AI attribution per commit: agent, model, line ranges, AI %, file paths |
| **GitHub** | Webhooks (PR events, reviews, review comments) | PR lifecycle timestamps, review comments with file/line positions, merge events |
| **Jira** | Polling every 15-30 min + on-demand sync | Issue metadata, status transitions with timestamps, sprint data, time logs, story points |
| **Webex** | Webhooks (messages.created) | Messages and thread replies in review spaces, timestamps for response time tracking |

### 2.1 git-ai Integration

Developers install git-ai (https://usegitai.com/), which tracks AI-generated code via Git Hooks and stores attribution in Git Notes (`refs/notes/ai`). A git post-push hook reads the attribution data and POSTs it to our ingestion API. The hook is distributed to the team via a shared `.githooks` directory or setup script.

### 2.2 GitHub Webhooks

The backend exposes `POST /webhooks/github` to receive:
- `pull_request` events (opened, closed, merged, review_requested)
- `pull_request_review` events (submitted, dismissed)
- `pull_request_review_comment` events (created) -- includes file path and line number

### 2.3 Jira Polling

A scheduled job polls the Jira REST API every 15-30 minutes for:
- Issue details and changelog (status transitions with timestamps)
- Sprint data (committed vs completed points)
- Worklogs (time tracking entries)

An on-demand sync can be triggered from the dashboard via a "Sync Now" button.

### 2.4 Webex Integration

The backend exposes `POST /webhooks/webex` to receive `messages.created` events. Webex API capabilities (verified against developer.webex.com):
- **List/search rooms** by team, type, or title -- to find a team's review space
- **Read messages** with timestamps and `parentId` for thread tracking
- **Webhooks** on `messages.created` for real-time notification of replies

**Limitation:** The Webex API does not have explicit reaction-tracking endpoints. We track "time to first thread reply" rather than "time to first reaction."

Each repository is configured with its dedicated Webex review room ID and optionally a discussion channel room ID.

## 3. Architecture

### 3.1 High-Level Flow

```
Data Sources          Backend Service              Storage & UI
─────────────         ───────────────              ────────────
Git post-push hook ─┐
                    ├──► Ingestion API ──► Enrichment Engine ──► Database
GitHub webhooks   ──┤    - /webhooks/github     - Join PR↔Issue↔AI      │
                    │    - /webhooks/webex       - Correlate reviews     │
Webex webhooks   ───┤    - /ingest/git-ai         with AI lines        │
                    │    - Jira sync scheduler  - Compute time-in-stage │
Jira (polling)   ───┘                                                   │
                                                                        ▼
                                                  Dashboard API ──► Dashboard UI
                                                  - /metrics/delivery
                                                  - /metrics/time-analysis
                                                  - /metrics/ai-impact
                                                  - /metrics/webex-response
```

### 3.2 Key Design Decisions

- **Near real-time ingestion:** Webhooks for GitHub, Webex, and git hook provide real-time data. Only Jira uses polling due to its less reliable webhook story.
- **Enrichment as a separate step:** Raw events are stored first, then joined and correlated. This decouples ingestion reliability from computation complexity.
- **Single database:** At the scale of one team and 5 repos, a single relational database is sufficient. No data warehouse needed.
- **API-first:** The dashboard consumes a REST API that could serve other tools or reports later.

## 4. Metrics

### 4.1 Pillar 1: Delivery Speed & Reliability

#### Cycle Time (per issue)
- **Formula:** `PR Merged Timestamp - Issue "In Progress" Timestamp`
- **Sub-stages:**
  - **Coding Time** = `First PR Created - Issue moved to "In Progress"` (Jira transitions + GitHub PR)
  - **Review Time** = `PR Approved Timestamp - First Review Requested Timestamp` (GitHub PR events)
  - **Waiting Time** = `Cycle Time - Coding Time - Review Time` (derived; includes queue time, CI, merge delays)

#### Velocity (per sprint)
- **Formula:** `Sum of story points of issues completed in sprint`
- **Source:** Jira
- **Segmentation:** AI-assisted vs non-AI issues

#### Sprint Completion Rate
- **Formula:** `(Issues Done in Sprint / Issues Committed to Sprint) x 100%`
- **Source:** Jira

#### PR Merge Rate
- **Formula:** `(PRs Merged / PRs Opened) x 100%`
- **Source:** GitHub

#### PR Throughput
- **Formula:** `Count of PRs merged per time window`
- **Source:** GitHub

### 4.2 Pillar 2: Where Time Is Spent & Where Work Gets Stuck

#### Time-in-Stage Distribution
- **Formula:** `% in Stage = (Avg Time in Stage / Avg Total Cycle Time) x 100%`
- **Source:** Jira + GitHub
- **Granularity levels:**
  - **Team** = Average across all issues in time window
  - **Developer** = Average across issues assigned to developer
  - **Issue** = Actual time per stage for a single issue

#### Review Queue Depth
- **Formula:** `Count of open PRs with review requested but no review submitted`
- **Source:** GitHub
- **Type:** Point-in-time snapshot

#### Review Pickup Time
- **Formula:** `First Review Comment Timestamp - Review Requested Timestamp`
- **Source:** GitHub
- **Supplemented by Webex:** `First Reply in Thread - Review Request Message Timestamp`
- Webex response time captures acknowledgment even before formal GitHub review begins.

#### Rework Rate
- **Formula:** `(PRs with "Changes Requested" / Total PRs Reviewed) x 100%`
- **Review Rounds:** `Count of review iterations before approval`
- **Source:** GitHub

#### Blocked Time
- **Formula:** `Time issue spent in "Blocked" status or with blocker flag`
- **Source:** Jira

### 4.3 Pillar 3: AI Impact

#### AI Code Contribution
- **Per commit:** `(AI-attributed lines / Total lines changed) x 100%`
- **Per PR:** `Sum of AI lines across commits / Sum of total lines across commits x 100%`
- **Team (period):** `Sum of AI lines merged / Sum of total lines merged x 100%`
- **Source:** git-ai
- **Segmentable by:** developer, repo, agent (Cursor/Claude/Copilot), model

#### AI vs Human: Review Comment Density (within same PR)
- **AI Comment Density** = `Review comments on AI-attributed lines / AI lines in PR`
- **Human Comment Density** = `Review comments on human lines / Human lines in PR`
- **Source:** git-ai + GitHub
- Requires matching GitHub review comment line positions against git-ai attribution ranges.

#### AI vs Human: Revision Rounds (within same PR)
- **AI Revision Rate** = `Commits that modify AI-attributed lines after review / Total review rounds`
- **Human Revision Rate** = `Commits that modify human lines after review / Total review rounds`
- **Source:** git-ai + GitHub
- Measures whether AI code requires more post-review fixes than human code.

#### AI vs Human: Review Turnaround
- **Formula:** `Avg Review Time (high-AI PRs) vs Avg Review Time (low-AI PRs)`
- **Source:** git-ai + GitHub
- Threshold-based: PRs with >50% AI code vs <20% AI code. Shows if reviewers treat AI-heavy PRs differently.

#### AI Tool & Model Usage
- **By agent:** `Count of commits per agent (Cursor, Claude Code, Copilot, etc.)`
- **By model:** `Count of commits per model (Sonnet, Opus, GPT-4, etc.)`
- **Source:** git-ai
- Tracks adoption trends and which tools the team gravitates toward.

#### AI Productivity Impact
- **Formula:** `Avg Coding Time (AI-assisted issues) vs Avg Coding Time (non-AI issues)`
- **Formula:** `Avg Cycle Time (AI-assisted issues) vs Avg Cycle Time (non-AI issues)`
- **Source:** git-ai + Jira
- An issue is "AI-assisted" if any of its linked PRs contain git-ai attributed code. Compare same issue types (bug vs bug, story vs story) for fairness.

### 4.4 Pillar 4: AI Quality & Oversight

Answers: "Is AI-generated code meeting our engineering standards?"

#### AI Code Defect Rate
- **Formula:** `(Bug-fix PRs that modify AI-attributed lines / Total PRs with AI code) x 100%`
- **Source:** git-ai + GitHub
- Tracks whether AI-generated code produces bugs at a higher rate than human code. Bug-fix PRs are identified by Jira issue type (Bug) linked to the PR.

#### AI Code Revert Rate
- **Formula:** `(Reverted commits containing AI-attributed lines / Total commits with AI code) x 100%`
- **Source:** git-ai + GitHub
- Measures how often AI-generated code gets reverted compared to human code. High revert rate suggests AI output is being accepted without sufficient review.

#### Unmodified AI Code Ratio (Copy-Paste Indicator)
- **Formula:** `(AI-attributed lines unchanged from generation to merge / Total AI-attributed lines) x 100%`
- **Source:** git-ai (comparing checkpoint snapshot to final committed code)
- **Interpretation requires context:** A high ratio is ambiguous on its own. It may indicate blind acceptance (risky) OR excellent spec/prompt engineering where the developer front-loaded their thinking into a precise specification and the AI output was correct first try (healthy). The dashboard must never flag this metric in isolation — it should always be evaluated alongside test coverage, review engagement, and defect history. See Oversight Flags (View 5) for the composite rule.

#### Review Depth on AI Code
- **Avg Review Comment Length:** Trended over time, segmented by AI-heavy PRs (>50% AI) vs non-AI PRs (<20% AI)
- **Review Comments per AI Line vs per Human Line:** Within the same PR
- **Source:** git-ai + GitHub
- Declining review depth on AI-heavy PRs is a leading indicator that reviewers are rubber-stamping AI output.

#### AI Review Blind Acceptance Rate
- **Formula:** `(AI review threads resolved in <2 min or with no reply / Total AI review threads) x 100%`
- **Source:** GitHub review threads (e.g., chatgpt-codex-connector threads)
- Tracks whether developers are dismissing automated AI review suggestions without reading them.

#### Prompt-to-Fix Cycle
- **Formula:** `Count of follow-up commits within 24h that modify AI-attributed lines from the same PR`
- **Source:** git-ai + GitHub
- Frequent immediate fixes to AI code suggest the original AI output was merged prematurely.

#### Test Coverage on AI Code
- **Formula:** `(Test lines added in PRs with AI code / AI lines added) vs (Test lines added in non-AI PRs / Code lines added)`
- **Source:** git-ai + GitHub (file path heuristic: files in test/, utest/, itest/ directories)
- Ensures AI-generated code is tested with the same rigor as human-written code.

#### Knowledge Concentration Risk
- **Formula:** `% of files in a module where >80% of recent changes come from a single author + AI`
- **Source:** git-ai + git blame
- Flags bus-factor risk where one developer + AI is writing most of a module, reducing shared understanding.

### 4.5 Webex Communication Metrics

#### Review Request Response Time
- **Formula:** `First Thread Reply Timestamp - Original Message Timestamp`
- **Source:** Webex
- Tracked in the team's dedicated review Webex space.

#### Communication-to-Action Gap
- **Formula:** `First GitHub Review Activity - First Webex Thread Reply on same PR`
- **Source:** Webex + GitHub
- Measures lag between "I'll look at it" (Webex ack) and actually reviewing (GitHub activity). Large gap indicates context switching or deprioritization.

## 5. Data Model

### 5.1 Jira-Sourced Entities

**Issue**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | Internal |
| jira_key | string | "PROJ-123" |
| title | string | |
| type | enum | bug, story, task |
| assignee | string | |
| story_points | number | |
| sprint_id | FK -> Sprint | |
| created_at | timestamp | |
| resolved_at | timestamp | |

**IssueTransition**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| issue_id | FK -> Issue | |
| from_status | string | "To Do" |
| to_status | string | "In Progress" |
| transitioned_at | timestamp | |

**Sprint**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| jira_sprint_id | string | |
| name | string | |
| start_date | date | |
| end_date | date | |
| committed_points | number | |
| completed_points | number | |

**TimeLog**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| issue_id | FK -> Issue | |
| author | string | |
| time_spent_seconds | number | |
| logged_at | timestamp | |

### 5.2 GitHub + git-ai Entities

**PullRequest**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| github_pr_number | number | |
| repo | string | |
| author | string | |
| issue_id | FK -> Issue | Nullable; linked via branch name or PR body |
| lines_added | number | |
| lines_removed | number | |
| ai_lines_added | number | From git-ai |
| ai_lines_removed | number | From git-ai |
| ai_percentage | number | Computed |
| created_at | timestamp | |
| first_review_requested_at | timestamp | |
| first_reviewed_at | timestamp | |
| approved_at | timestamp | |
| merged_at | timestamp | |

**Commit**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| sha | string | |
| pr_id | FK -> PullRequest | |
| author | string | |
| lines_added | number | |
| lines_removed | number | |
| committed_at | timestamp | |

**AIAttribution**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| commit_id | FK -> Commit | |
| agent | string | cursor, claude, copilot, etc. |
| model | string | sonnet-4, gpt-4, etc. |
| ai_lines_start | number | Line range start |
| ai_lines_end | number | Line range end |
| file_path | string | |
| total_ai_lines | number | |
| total_lines_in_commit | number | |
| ai_percentage | number | |

**ReviewComment**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| pr_id | FK -> PullRequest | |
| author | string | |
| file_path | string | |
| line_number | number | |
| is_on_ai_code | boolean | Enriched: matched against AIAttribution ranges |
| review_round | number | Enriched: which review iteration |
| created_at | timestamp | |

### 5.3 Webex + Computed Entities

**WebexMessage**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| webex_message_id | string | |
| room_id | string | |
| room_name | string | |
| pr_id | FK -> PullRequest | Nullable; matched by PR URL in message |
| author | string | |
| parent_message_id | string | Thread parent |
| is_review_request | boolean | Enriched |
| created_at | timestamp | |

**IssueCycleMetrics** (materialized/computed)
| Field | Type | Notes |
|-------|------|-------|
| issue_id | FK -> Issue | |
| coding_time_hours | number | |
| review_time_hours | number | |
| waiting_time_hours | number | |
| total_cycle_time_hours | number | |
| is_ai_assisted | boolean | True if any linked PR has AI attribution |
| ai_percentage | number | Average across linked PRs |
| review_rounds | number | |
| ai_comment_density | number | |
| human_comment_density | number | |
| webex_response_time_hours | number | |
| computed_at | timestamp | Recomputed on each relevant event |

**AIQualityMetrics** (materialized/computed per PR)
| Field | Type | Notes |
|-------|------|-------|
| pr_id | FK -> PullRequest | |
| ai_lines_unchanged | number | AI lines accepted as-is without human edits |
| ai_lines_modified | number | AI lines human-edited before merge |
| unmodified_ai_ratio | number | Computed: unchanged / total AI lines |
| ai_review_blind_accepts | number | AI review threads resolved <2 min or no reply |
| ai_review_total_threads | number | Total AI-generated review threads |
| followup_fixes_24h | number | Commits modifying AI lines within 24h of merge |
| test_lines_added | number | Test file lines added in this PR |
| has_tests_for_ai_code | boolean | True if test lines added cover AI-attributed files |
| reverted_within_7d | boolean | True if AI-attributed lines reverted within 7 days |
| defect_linked | boolean | True if a Bug issue is later linked to this PR |
| computed_at | timestamp | Recomputed on each relevant event |

**Developer**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| name | string | |
| github_username | string | |
| jira_account_id | string | |
| webex_person_id | string | |

**Repository**
| Field | Type | Notes |
|-------|------|-------|
| id | PK | |
| github_repo | string | owner/name |
| webex_review_room_id | string | Dedicated review space |
| webex_discussion_room_id | string | General discussion channel |
| jira_project_key | string | |

### 5.4 Key Relationships

- Issue 1 -> N PullRequest (via Jira key in branch name or PR body)
- PullRequest 1 -> N Commit
- Commit 1 -> N AIAttribution (per-file line ranges)
- PullRequest 1 -> N ReviewComment
- Issue 1 -> N IssueTransition
- Issue 1 -> N TimeLog
- Sprint 1 -> N Issue
- PullRequest 1 -> N WebexMessage (matched by PR URL in message content)
- Issue 1 -> 1 IssueCycleMetrics (materialized view)
- PullRequest 1 -> 1 AIQualityMetrics (materialized view, computed per PR)
- Developer maps identities across GitHub, Jira, and Webex

### 5.5 Enrichment Logic

- **Issue-PR linking:** Match Jira key in branch name (e.g., `feature/PROJ-123-...`) or PR body
- **Review comment-AI code correlation:** Match review comment's file_path + line_number against AIAttribution line ranges for that commit
- **Webex-PR linking:** Detect PR URLs in Webex messages to associate with PullRequest records
- **IssueCycleMetrics:** Recomputed on each new event (transition, PR merge, review) for the affected issue
- **AIQualityMetrics:** Computed per PR on merge. Compares git-ai checkpoint snapshot against final committed code to determine unmodified ratio. Monitors for reverts and bug-linked issues within 7-day window post-merge. AI review thread resolution times computed from GitHub review comment timestamps.
- **Developer identity:** Single mapping table unifies GitHub username, Jira account, and Webex person ID

## 6. Dashboard Views

### 6.1 Global Controls (present on every page)

- **Date range picker:** Flexible start/end dates
- **Granularity selector:** Daily, weekly, sprint, monthly
- **Repo filter:** All or specific repository
- **Developer filter:** All or specific developer
- **Sync Now button:** Triggers on-demand Jira sync

### 6.2 View 1: Overview (Landing Page)

Executive-friendly snapshot. Four KPI cards with period-over-period comparison:
- Avg Cycle Time (with trend arrow)
- AI Code % (with trend arrow)
- Sprint Completion Rate (with trend arrow)
- Review Pickup Time (with trend arrow)

Summary charts:
- Cycle Time Trend (bar chart over selected time windows)
- Time Distribution (stacked bar: coding % / review % / waiting %)

### 6.3 View 2: Delivery

Answers: "Are we delivering faster and more reliably?"

Charts:
- **Velocity Trend:** Story points per sprint, with AI-assisted vs non-AI overlay (stacked bar)
- **Sprint Completion Rate:** % done vs committed, trend over sprints (line chart with target)
- **PR Throughput & Merge Rate:** PRs opened vs merged per period (dual-axis chart)
- **Cycle Time Breakdown:** Coding + review + waiting stacked over time (stacked area chart)

### 6.4 View 3: Bottlenecks

Answers: "Where is time being spent and where is work getting stuck?"

Charts:
- **Time-in-Stage:** Team aggregate with click-to-expand per-developer breakdown (stacked horizontal bar)
- **Review Queue & Pickup Time:** Current queue depth + avg pickup trend (combo bar + line)
- **Rework Rate:** % PRs needing changes + avg review rounds (line chart)
- **Webex Response Times:** Time to acknowledge + communication-to-action gap (dual line)

Table:
- **Currently Stuck Items:** Issues and PRs exceeding configurable thresholds, showing item, stage, time-in-stage, assignee, and "Nudge via Webex" action button (stretch feature)

### 6.5 View 4: AI Impact

Answers: "How is AI helping?"

KPI cards:
- AI Code Merged (% of total lines this period)
- Top Agent (most used AI tool)
- AI Coding Time Saved (avg difference vs non-AI issues)

Charts:
- **AI Code % Trend:** % of AI-generated lines merged over time, by repo (multi-line chart)
- **AI vs Human: Review Quality:** Comment density + revision rounds comparison within same PR (grouped bar)
- **Tool & Model Adoption:** Which agents and models the team uses over time (stacked area)
- **AI Productivity Comparison:** Cycle time for AI-assisted vs non-AI issues, by issue type (grouped bar)

### 6.6 View 5: AI Quality & Oversight

Answers: "Is AI-generated code meeting our engineering standards?"

KPI cards:
- AI Defect Rate (% of bug-fix PRs targeting AI-attributed code vs human code)
- Unmodified AI Ratio (% of AI code accepted as-is without human edits)
- Review Depth Trend (trending direction of review thoroughness on AI-heavy PRs)

Charts:
- **AI Code Quality:** Defect rate + revert rate for AI code vs human code (grouped bar, same issue types compared for fairness)
- **Code Understanding:** Unmodified AI code ratio trend over time, with threshold line at team-defined acceptable level (line chart)
- **Review Thoroughness:** Review comment depth + AI blind acceptance rate, trended over time (dual line chart)
- **Test Rigor:** Test-lines-per-code-line ratio for AI PRs vs non-AI PRs (grouped bar)

Table:
- **Oversight Flags:** PRs where >80% AI code AND zero human edits to AI lines AND no new tests added. Columns: PR, Author, AI %, Human Edits, Tests Added, Flag Reason

### 6.7 Drill-Down Pattern

All views support progressive drill-down:
- Click any chart segment to filter to that dimension
- Team view -> click developer name -> developer detail view
- Developer detail -> click issue -> issue timeline
- Issue timeline shows full stage-by-stage breakdown with timestamps

## 7. Stretch Features

These are designed for but not part of the core build:

### 7.1 Webex Automated Alerts
- Configurable via config file (not UI for v1)
- Rules post to the team's review Webex space when thresholds are exceeded (e.g., PR waiting for review > 3 days)

### 7.2 Manual Webex Nudge
- "Nudge via Webex" button on the stuck items table in the Bottlenecks view
- Sends a reminder message to the review space tagging the relevant reviewer

### 7.3 Escalation to Discussion Channel
- If no response in the review space after a configurable threshold, auto-post to the team's general discussion channel

## 8. Visual References

Standalone HTML mockups are available in `docs/visuals/`:
- `standalone-architecture.html` -- System architecture diagram
- `standalone-metrics.html` -- All metrics with formulas and sources
- `standalone-dashboard-views.html` -- Dashboard page mockups
- `standalone-data-model.html` -- Entity relationship diagram

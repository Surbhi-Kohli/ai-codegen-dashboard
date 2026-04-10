"""
B11: Dashboard Read Endpoints

REST API serving pre-computed data for all 5 dashboard views.
Supports filters: date range, repo, developer.
"""
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AIAttribution,
    AIQualityMetrics,
    Commit,
    Issue,
    IssueCycleMetrics,
    IssueTransition,
    PullRequest,
    Repository,
    ReviewComment,
    Sprint,
    WebexMessage,
)
from app.db.session import get_db

# Status values that indicate "done"
DONE_STATUSES = {"done", "closed", "resolved", "complete", "completed"}

router = APIRouter()


# ── Common filter params ─────────────────────────────────────────────


def _date_filter(model_col, start: date | None, end: date | None):
    """Build date range filter conditions."""
    conditions = []
    if start:
        conditions.append(model_col >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc))
    if end:
        conditions.append(model_col <= datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc))
    return conditions


# ── View 1: Overview ─────────────────────────────────────────────────


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    repo: str | None = Query(None),
):
    """KPI cards + summary for the overview page."""
    date_conds = _date_filter(Issue.created_at, start_date, end_date)

    # Total issues
    q = select(func.count(Issue.id))
    if date_conds:
        q = q.where(and_(*date_conds))
    total_issues = (await db.execute(q)).scalar() or 0

    # Resolved issues
    resolved_conds = _date_filter(Issue.resolved_at, start_date, end_date)
    q = select(func.count(Issue.id)).where(Issue.resolved_at.isnot(None))
    if resolved_conds:
        q = q.where(and_(*resolved_conds))
    resolved_issues = (await db.execute(q)).scalar() or 0

    # Average cycle time
    q = select(func.avg(IssueCycleMetrics.total_cycle_time_hours))
    avg_cycle_time = (await db.execute(q)).scalar()

    # PRs merged
    pr_date_conds = _date_filter(PullRequest.merged_at, start_date, end_date)
    q = select(func.count(PullRequest.id)).where(PullRequest.merged_at.isnot(None))
    if pr_date_conds:
        q = q.where(and_(*pr_date_conds))
    prs_merged = (await db.execute(q)).scalar() or 0

    # AI-assisted %
    q = select(func.count(IssueCycleMetrics.id)).where(IssueCycleMetrics.is_ai_assisted == True)  # noqa: E712
    ai_assisted_count = (await db.execute(q)).scalar() or 0
    total_metrics = (await db.execute(select(func.count(IssueCycleMetrics.id)))).scalar() or 1
    ai_assisted_pct = round(ai_assisted_count / total_metrics * 100, 1)

    return {
        "kpis": {
            "total_issues": total_issues,
            "resolved_issues": resolved_issues,
            "avg_cycle_time_hours": round(avg_cycle_time, 1) if avg_cycle_time else None,
            "prs_merged": prs_merged,
            "ai_assisted_pct": ai_assisted_pct,
        }
    }


# ── View 2: Delivery ────────────────────────────────────────────────


@router.get("/delivery")
async def delivery(
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Delivery speed & reliability metrics."""
    # Cycle time breakdown (avg coding, review, waiting)
    q = select(
        func.avg(IssueCycleMetrics.coding_time_hours),
        func.avg(IssueCycleMetrics.review_time_hours),
        func.avg(IssueCycleMetrics.waiting_time_hours),
        func.avg(IssueCycleMetrics.total_cycle_time_hours),
    )
    row = (await db.execute(q)).one_or_none()

    cycle_breakdown = {
        "avg_coding_hours": round(row[0], 1) if row and row[0] else None,
        "avg_review_hours": round(row[1], 1) if row and row[1] else None,
        "avg_waiting_hours": round(row[2], 1) if row and row[2] else None,
        "avg_total_hours": round(row[3], 1) if row and row[3] else None,
    }

    # PR throughput (merged per week — simplified)
    pr_date_conds = _date_filter(PullRequest.merged_at, start_date, end_date)
    q = select(func.count(PullRequest.id)).where(PullRequest.merged_at.isnot(None))
    if pr_date_conds:
        q = q.where(and_(*pr_date_conds))
    prs_merged = (await db.execute(q)).scalar() or 0

    return {
        "cycle_breakdown": cycle_breakdown,
        "prs_merged": prs_merged,
    }


# ── View 3: Bottlenecks ─────────────────────────────────────────────


@router.get("/bottlenecks")
async def bottlenecks(
    db: AsyncSession = Depends(get_db),
):
    """Where time is spent & where work gets stuck."""
    # Review queue depth: open PRs with no review
    q = select(func.count(PullRequest.id)).where(
        PullRequest.state == "open",
        PullRequest.first_review_at.is_(None),
    )
    review_queue = (await db.execute(q)).scalar() or 0

    # Average review rounds (rework rate)
    q = select(func.avg(IssueCycleMetrics.review_rounds))
    avg_review_rounds = (await db.execute(q)).scalar()

    # Time-in-stage distribution
    q = select(
        func.avg(IssueCycleMetrics.coding_time_hours),
        func.avg(IssueCycleMetrics.review_time_hours),
        func.avg(IssueCycleMetrics.waiting_time_hours),
    )
    row = (await db.execute(q)).one_or_none()

    total = sum(v or 0 for v in (row[0], row[1], row[2])) if row else 0
    stage_distribution = {}
    if total > 0 and row:
        stage_distribution = {
            "coding_pct": round((row[0] or 0) / total * 100, 1),
            "review_pct": round((row[1] or 0) / total * 100, 1),
            "waiting_pct": round((row[2] or 0) / total * 100, 1),
        }

    # Time waiting for AI (from git-ai stats on commits)
    q = select(func.avg(IssueCycleMetrics.total_time_waiting_for_ai_secs)).where(
        IssueCycleMetrics.total_time_waiting_for_ai_secs.isnot(None)
    )
    avg_ai_wait_secs = (await db.execute(q)).scalar()

    return {
        "review_queue_depth": review_queue,
        "avg_review_rounds": round(avg_review_rounds, 1) if avg_review_rounds else None,
        "stage_distribution": stage_distribution,
        "avg_time_waiting_for_ai_secs": round(avg_ai_wait_secs, 0) if avg_ai_wait_secs else None,
    }


# ── View 4: AI Impact ───────────────────────────────────────────────


@router.get("/ai-impact")
async def ai_impact(
    db: AsyncSession = Depends(get_db),
):
    """AI contribution, tool adoption, productivity comparison."""
    # Avg AI percentage -- try PR-level first, fall back to commit-level
    q = select(func.avg(PullRequest.ai_percentage)).where(
        PullRequest.ai_percentage.isnot(None),
    )
    avg_ai_pct = (await db.execute(q)).scalar()

    if avg_ai_pct is None:
        q = select(
            func.sum(Commit.ai_additions),
            func.sum(Commit.human_additions),
            func.sum(Commit.mixed_additions),
        ).where(Commit.ai_additions.isnot(None))
        row = (await db.execute(q)).one_or_none()
        if row and row[0]:
            total_ai = (row[0] or 0) + (row[2] or 0)
            total_all = total_ai + (row[1] or 0)
            if total_all > 0:
                avg_ai_pct = total_ai / total_all * 100

    # Top agents (most used AI tools)
    q = (
        select(AIAttribution.agent, func.count(AIAttribution.id).label("count"))
        .group_by(AIAttribution.agent)
        .order_by(func.count(AIAttribution.id).desc())
        .limit(5)
    )
    agent_rows = (await db.execute(q)).all()
    top_agents = [{"agent": row[0], "count": row[1]} for row in agent_rows]

    # AI vs non-AI cycle time comparison
    q_ai = select(func.avg(IssueCycleMetrics.total_cycle_time_hours)).where(
        IssueCycleMetrics.is_ai_assisted == True  # noqa: E712
    )
    q_non_ai = select(func.avg(IssueCycleMetrics.total_cycle_time_hours)).where(
        IssueCycleMetrics.is_ai_assisted == False  # noqa: E712
    )
    avg_ai_cycle = (await db.execute(q_ai)).scalar()
    avg_non_ai_cycle = (await db.execute(q_non_ai)).scalar()

    # AI Accepted Ratio (from git-ai stats on commits)
    q = select(
        func.sum(Commit.ai_accepted),
        func.sum(Commit.mixed_additions),
    ).where(Commit.ai_accepted.isnot(None))
    row = (await db.execute(q)).one_or_none()
    total_accepted = (row[0] or 0) if row else 0
    total_mixed = (row[1] or 0) if row else 0
    total_ai_code = total_accepted + total_mixed
    ai_accepted_ratio = round(total_accepted / total_ai_code * 100, 1) if total_ai_code > 0 else None

    # Time waiting for AI aggregated
    q = select(func.avg(Commit.time_waiting_for_ai_secs)).where(
        Commit.time_waiting_for_ai_secs.isnot(None),
        Commit.time_waiting_for_ai_secs > 0,
    )
    avg_wait_secs = (await db.execute(q)).scalar()

    # Tool/model breakdown aggregated from all commits
    q = select(Commit.tool_model_breakdown).where(Commit.tool_model_breakdown.isnot(None))
    breakdown_rows = (await db.execute(q)).scalars().all()
    tool_model_totals: dict[str, dict] = {}
    for raw in breakdown_rows:
        try:
            parsed = json.loads(raw)

            entries: list[dict] = []
            if isinstance(parsed, list):
                entries = parsed
            elif isinstance(parsed, dict):
                # git-ai v3.0.0: {"tool::model": {stats...}}
                for compound_key, stats in parsed.items():
                    if isinstance(stats, dict):
                        parts = compound_key.split("::", 1)
                        tool = parts[0] if parts else "unknown"
                        model = parts[1] if len(parts) > 1 else "unknown"
                        entries.append({"tool": tool, "model": model, **stats})

            for entry in entries:
                key = f"{entry.get('tool', 'unknown')}/{entry.get('model', 'unknown')}"
                if key not in tool_model_totals:
                    tool_model_totals[key] = {"tool": entry.get("tool"), "model": entry.get("model"), "additions": 0, "accepted": 0}
                tool_model_totals[key]["additions"] += entry.get("ai_additions", entry.get("additions", 0))
                tool_model_totals[key]["accepted"] += entry.get("ai_accepted", entry.get("accepted", 0))
        except (json.JSONDecodeError, TypeError):
            continue
    tool_model_stats = sorted(tool_model_totals.values(), key=lambda x: x["additions"], reverse=True)

    # ── Per-file AI attribution heatmap ──
    file_q = (
        select(
            AIAttribution.file_path,
            func.count(AIAttribution.id).label("regions"),
            func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).label("ai_lines"),
            AIAttribution.agent,
            AIAttribution.model,
        )
        .group_by(AIAttribution.file_path, AIAttribution.agent, AIAttribution.model)
        .order_by(func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).desc())
    )
    file_rows = (await db.execute(file_q)).all()
    file_heatmap = [
        {
            "file": r[0],
            "regions": r[1],
            "ai_lines": int(r[2]) if r[2] else 0,
            "agent": r[3],
            "model": r[4],
        }
        for r in file_rows
    ]

    # ── Per-file line ranges (drill-down detail) ──
    range_q = (
        select(
            AIAttribution.file_path,
            AIAttribution.ai_lines_start,
            AIAttribution.ai_lines_end,
            AIAttribution.agent,
            AIAttribution.model,
            AIAttribution.prompt_id,
            Commit.sha,
        )
        .join(Commit, Commit.id == AIAttribution.commit_id)
        .order_by(AIAttribution.file_path, AIAttribution.ai_lines_start)
    )
    range_rows = (await db.execute(range_q)).all()
    file_ranges: dict[str, list] = {}
    for r in range_rows:
        fp = r[0]
        if fp not in file_ranges:
            file_ranges[fp] = []
        file_ranges[fp].append({
            "start": r[1],
            "end": r[2],
            "lines": r[2] - r[1] + 1,
            "agent": r[3],
            "model": r[4],
            "prompt_id": r[5],
            "commit": r[6][:12] if r[6] else None,
        })

    # ── Commit timeline (all commits, AI and human, excluding git-notes bookkeeping) ──
    commit_q = (
        select(Commit)
        .where(~Commit.message.like("Notes %by 'git notes%'"))
        .order_by(Commit.committed_at.desc())
    )
    commit_rows = (await db.execute(commit_q)).scalars().all()
    commit_timeline = []
    for c in commit_rows:
        tmb = {}
        if c.tool_model_breakdown:
            try:
                tmb = json.loads(c.tool_model_breakdown)
            except (json.JSONDecodeError, TypeError):
                pass
        models_used = []
        if isinstance(tmb, dict):
            for k in tmb:
                parts = k.split("::", 1)
                models_used.append(parts[1] if len(parts) > 1 else k)

        commit_timeline.append({
            "sha": c.sha[:12],
            "message": c.message[:80],
            "author": c.author,
            "committed_at": c.committed_at.isoformat() if c.committed_at else None,
            "ai_additions": c.ai_additions,
            "human_additions": c.human_additions,
            "ai_accepted": c.ai_accepted,
            "models": models_used,
            "time_waiting_secs": c.time_waiting_for_ai_secs,
        })

    # ── Prompt activity (group by prompt ID) ──
    prompt_q = (
        select(
            AIAttribution.prompt_id,
            AIAttribution.agent,
            AIAttribution.model,
            AIAttribution.human_author,
            func.count(AIAttribution.id).label("regions"),
            func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).label("total_lines"),
            func.group_concat(AIAttribution.file_path.distinct()).label("files"),
        )
        .where(AIAttribution.prompt_id.isnot(None))
        .group_by(AIAttribution.prompt_id, AIAttribution.agent, AIAttribution.model, AIAttribution.human_author)
        .order_by(func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).desc())
    )
    prompt_rows = (await db.execute(prompt_q)).all()
    prompt_activity = [
        {
            "prompt_id": r[0][:16] if r[0] else None,
            "agent": r[1],
            "model": r[2],
            "author": r[3],
            "regions": r[4],
            "total_lines": int(r[5]) if r[5] else 0,
            "files": r[6].split(",") if r[6] else [],
        }
        for r in prompt_rows
    ]

    # ── Author AI contributions ──
    author_q = (
        select(
            AIAttribution.human_author,
            AIAttribution.agent,
            func.count(AIAttribution.id).label("attributions"),
            func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).label("ai_lines"),
        )
        .where(AIAttribution.human_author.isnot(None))
        .group_by(AIAttribution.human_author, AIAttribution.agent)
        .order_by(func.sum(AIAttribution.ai_lines_end - AIAttribution.ai_lines_start + 1).desc())
    )
    author_rows = (await db.execute(author_q)).all()
    author_contributions = [
        {
            "author": r[0],
            "agent": r[1],
            "attributions": r[2],
            "ai_lines": int(r[3]) if r[3] else 0,
        }
        for r in author_rows
    ]

    return {
        "avg_ai_code_pct": round(avg_ai_pct, 1) if avg_ai_pct else None,
        "top_agents": top_agents,
        "productivity_comparison": {
            "ai_assisted_avg_hours": round(avg_ai_cycle, 1) if avg_ai_cycle else None,
            "non_ai_avg_hours": round(avg_non_ai_cycle, 1) if avg_non_ai_cycle else None,
        },
        "ai_accepted_ratio": ai_accepted_ratio,
        "ai_accepted_vs_edited": {
            "accepted": total_accepted,
            "human_edited": total_mixed,
        },
        "avg_time_waiting_for_ai_secs": round(avg_wait_secs, 0) if avg_wait_secs else None,
        "tool_model_breakdown": tool_model_stats,
        "file_heatmap": file_heatmap,
        "file_ranges": file_ranges,
        "commit_timeline": commit_timeline,
        "prompt_activity": prompt_activity,
        "author_contributions": author_contributions,
    }


# ── View 5: AI Quality & Oversight ──────────────────────────────────


@router.get("/ai-quality")
async def ai_quality(
    db: AsyncSession = Depends(get_db),
):
    """AI quality signals, oversight flags, and risk metrics."""
    # Defect rate on AI code
    total_ai_prs = (await db.execute(
        select(func.count(AIQualityMetrics.id))
    )).scalar() or 1
    defect_count = (await db.execute(
        select(func.count(AIQualityMetrics.id)).where(
            AIQualityMetrics.defect_linked == True  # noqa: E712
        )
    )).scalar() or 0
    defect_rate = round(defect_count / total_ai_prs * 100, 1)

    # Revert rate
    revert_count = (await db.execute(
        select(func.count(AIQualityMetrics.id)).where(
            AIQualityMetrics.reverted_within_7d == True  # noqa: E712
        )
    )).scalar() or 0
    revert_rate = round(revert_count / total_ai_prs * 100, 1)

    # Avg unmodified AI ratio
    avg_unmodified = (await db.execute(
        select(func.avg(AIQualityMetrics.unmodified_ai_ratio))
    )).scalar()

    # Blind acceptance rate
    total_threads = (await db.execute(
        select(func.sum(AIQualityMetrics.ai_review_total_threads))
    )).scalar() or 1
    total_blind = (await db.execute(
        select(func.sum(AIQualityMetrics.ai_review_blind_accepts))
    )).scalar() or 0
    blind_accept_rate = round(total_blind / total_threads * 100, 1) if total_threads > 0 else 0

    # Test coverage flag
    no_test_count = (await db.execute(
        select(func.count(AIQualityMetrics.id)).where(
            AIQualityMetrics.has_tests_for_ai_code == False  # noqa: E712
        )
    )).scalar() or 0
    no_test_pct = round(no_test_count / total_ai_prs * 100, 1)

    # Oversight flags: PRs with high AI + no tests + low modification
    # (composite rule — never flag on single metric alone)
    flags_result = await db.execute(
        select(AIQualityMetrics, PullRequest)
        .join(PullRequest, PullRequest.id == AIQualityMetrics.pr_id)
        .where(
            PullRequest.ai_percentage > 80,
            AIQualityMetrics.has_tests_for_ai_code == False,  # noqa: E712
        )
        .order_by(PullRequest.merged_at.desc())
        .limit(20)
    )
    flagged_prs = []
    for qm, pr in flags_result.all():
        flagged_prs.append({
            "pr_number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "ai_pct": pr.ai_percentage,
            "has_tests": qm.has_tests_for_ai_code,
            "unmodified_ratio": qm.unmodified_ai_ratio,
            "blind_accepts": qm.ai_review_blind_accepts,
            "reverted": qm.reverted_within_7d,
            "defect_linked": qm.defect_linked,
        })

    return {
        "kpis": {
            "ai_defect_rate": defect_rate,
            "ai_revert_rate": revert_rate,
            "avg_unmodified_ratio": round(avg_unmodified, 1) if avg_unmodified else None,
            "blind_acceptance_rate": blind_accept_rate,
            "prs_without_tests_pct": no_test_pct,
        },
        "oversight_flags": flagged_prs,
    }


# ── Issue-level detail (drill-down) ─────────────────────────────────


@router.get("/issues/{jira_key}")
async def issue_detail(
    jira_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Full detail view for a single issue: timeline, PRs, metrics."""
    result = await db.execute(select(Issue).where(Issue.jira_key == jira_key))
    issue = result.scalar_one_or_none()
    if not issue:
        return {"error": "Issue not found"}

    # Transitions timeline
    trans_result = await db.execute(
        select(IssueTransition)
        .where(IssueTransition.issue_id == issue.id)
        .order_by(IssueTransition.transitioned_at)
    )
    transitions = [
        {
            "from": t.from_status,
            "to": t.to_status,
            "at": t.transitioned_at.isoformat(),
        }
        for t in trans_result.scalars().all()
    ]

    # Linked PRs
    prs_result = await db.execute(
        select(PullRequest).where(PullRequest.issue_id == issue.id)
    )
    prs = [
        {
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "state": pr.state,
            "ai_percentage": pr.ai_percentage,
            "opened_at": pr.opened_at.isoformat() if pr.opened_at else None,
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        }
        for pr in prs_result.scalars().all()
    ]

    # Cycle metrics
    metrics_result = await db.execute(
        select(IssueCycleMetrics).where(IssueCycleMetrics.issue_id == issue.id)
    )
    metrics = metrics_result.scalar_one_or_none()
    metrics_data = None
    if metrics:
        metrics_data = {
            "coding_time_hours": metrics.coding_time_hours,
            "review_time_hours": metrics.review_time_hours,
            "waiting_time_hours": metrics.waiting_time_hours,
            "total_cycle_time_hours": metrics.total_cycle_time_hours,
            "is_ai_assisted": metrics.is_ai_assisted,
            "ai_percentage": metrics.ai_percentage,
            "ai_accepted_ratio": metrics.ai_accepted_ratio,
            "total_time_waiting_for_ai_secs": metrics.total_time_waiting_for_ai_secs,
            "primary_tool": metrics.primary_tool,
            "review_rounds": metrics.review_rounds,
        }

    return {
        "issue": {
            "jira_key": issue.jira_key,
            "type": issue.issue_type,
            "summary": issue.summary,
            "status": issue.status,
            "created_at": issue.created_at.isoformat(),
            "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
        },
        "transitions": transitions,
        "pull_requests": prs,
        "cycle_metrics": metrics_data,
    }


# ── Webex notifications ──────────────────────────────────────────


@router.post("/notify-pr/{pr_id}")
async def send_webex_pr_notification(
    pr_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Send a Webex message summarizing AI attribution for a PR."""
    from app.integrations.webex_notifier import notify_pr
    result = await notify_pr(db, pr_id)
    return result


@router.post("/notify-overview")
async def send_webex_overview(
    db: AsyncSession = Depends(get_db),
):
    """Send a team overview summary to Webex."""
    from app.config import settings
    import httpx

    if not settings.webex_bot_token or not settings.webex_review_room_id:
        return {"status": "skipped", "reason": "Webex not configured"}

    total_issues = (await db.execute(select(func.count(Issue.id)))).scalar() or 0
    resolved_issues = (await db.execute(
        select(func.count(Issue.id)).where(Issue.resolved_at.isnot(None))
    )).scalar() or 0

    merged_count = (await db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.merged_at.isnot(None))
    )).scalar() or 0
    open_count = (await db.execute(
        select(func.count(PullRequest.id)).where(
            PullRequest.state == "open", PullRequest.merged_at.is_(None)
        )
    )).scalar() or 0

    avg_ai_pct = (await db.execute(
        select(func.avg(PullRequest.ai_percentage)).where(PullRequest.ai_percentage.isnot(None))
    )).scalar()

    avg_cycle = (await db.execute(
        select(func.avg(IssueCycleMetrics.total_cycle_time_hours))
    )).scalar()

    msg = f"""**Team Overview Summary**
---
| Metric | Value |
|---|---|
| Issues Resolved | {resolved_issues} / {total_issues} |
| PRs Merged | {merged_count} |
| PRs Open | {open_count} |
| Avg AI Code | {round(avg_ai_pct, 1) if avg_ai_pct else '—'}% |
| Avg Cycle Time | {round(avg_cycle, 1) if avg_cycle else '—'}h |

_Sent from AI Codegen Dashboard_"""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://webexapis.com/v1/messages",
            headers={"Authorization": f"Bearer {settings.webex_bot_token}"},
            json={"roomId": settings.webex_review_room_id, "markdown": msg},
            timeout=15,
        )
    if resp.status_code in (200, 201):
        return {"status": "sent"}
    return {"status": "error", "reason": resp.text}


@router.get("/prs")
async def list_prs(
    db: AsyncSession = Depends(get_db),
):
    """List all PRs for the notification dropdown."""
    prs = (await db.execute(
        select(PullRequest).order_by(PullRequest.opened_at.desc()).limit(20)
    )).scalars().all()
    return [
        {
            "id": pr.id,
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "state": pr.state,
            "ai_percentage": pr.ai_percentage,
        }
        for pr in prs
    ]


@router.get("/boards")
async def list_boards(db: AsyncSession = Depends(get_db)):
    """Return distinct Jira project keys with issue counts."""
    rows = (await db.execute(
        select(
            func.substr(Issue.jira_key, 1, func.instr(Issue.jira_key, "-") - 1).label("key"),
            func.count().label("cnt"),
        )
        .where(Issue.jira_key.isnot(None))
        .group_by("key")
        .order_by(func.count().desc())
    )).all()
    return [{"key": r.key, "issue_count": r.cnt} for r in rows if r.key]


# ── Enrichment triggers ──────────────────────────────────────────


@router.post("/recompute-metrics")
async def recompute_metrics(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger recomputation of all cycle metrics."""
    from app.enrichment.cycle_metrics import recompute_all

    async def run_recompute():
        async with db.begin():
            count = await recompute_all(db)
            return count

    background_tasks.add_task(run_recompute)
    return {"status": "started", "message": "Cycle metrics recomputation started"}


# ── View 6: Webex Response Times ─────────────────────────────────────


@router.get("/webex-response")
async def webex_response(
    db: AsyncSession = Depends(get_db),
):
    """Webex communication metrics - response times and PR acknowledgment."""
    # Total messages tracked
    total_messages = (await db.execute(
        select(func.count(WebexMessage.id))
    )).scalar() or 0

    # Messages linked to PRs
    linked_to_prs = (await db.execute(
        select(func.count(WebexMessage.id)).where(
            WebexMessage.pull_request_id.isnot(None)
        )
    )).scalar() or 0

    # PR review request messages (messages with PR links that have thread replies)
    # A "review request" is a root message (no parent) that contains a PR URL
    review_requests = (await db.execute(
        select(func.count(WebexMessage.id)).where(
            WebexMessage.pull_request_id.isnot(None),
            WebexMessage.parent_message_id.is_(None),
        )
    )).scalar() or 0

    # Thread replies (messages with parent_message_id set)
    thread_replies = (await db.execute(
        select(func.count(WebexMessage.id)).where(
            WebexMessage.parent_message_id.isnot(None)
        )
    )).scalar() or 0

    # Calculate average response time for PR-related threads
    # Find review request messages and their first replies
    from sqlalchemy.orm import aliased

    ParentMsg = aliased(WebexMessage)
    ReplyMsg = aliased(WebexMessage)

    # Get pairs of (parent PR message, first reply)
    subq = (
        select(
            ParentMsg.id.label("parent_id"),
            func.min(ReplyMsg.created_at).label("first_reply_at"),
        )
        .join(ReplyMsg, ReplyMsg.parent_message_id == ParentMsg.webex_message_id)
        .where(
            ParentMsg.pull_request_id.isnot(None),
            ParentMsg.parent_message_id.is_(None),
        )
        .group_by(ParentMsg.id)
        .subquery()
    )

    # Calculate response times
    response_times_result = await db.execute(
        select(
            ParentMsg.id,
            ParentMsg.created_at,
            subq.c.first_reply_at,
        )
        .join(subq, subq.c.parent_id == ParentMsg.id)
    )

    response_times = []
    for row in response_times_result.all():
        if row[1] and row[2]:
            delta_hours = (row[2] - row[1]).total_seconds() / 3600
            response_times.append(delta_hours)

    avg_response_hours = None
    if response_times:
        avg_response_hours = round(sum(response_times) / len(response_times), 2)

    # Recent review requests (root messages) with response status
    # Show all root messages, not just PR-linked ones
    recent_result = await db.execute(
        select(WebexMessage)
        .where(
            WebexMessage.parent_message_id.is_(None),
        )
        .order_by(WebexMessage.created_at.desc())
        .limit(20)
    )

    recent_reviews = []
    for msg in recent_result.scalars().all():
        # Check if this message has any replies
        reply_count = (await db.execute(
            select(func.count(WebexMessage.id)).where(
                WebexMessage.parent_message_id == msg.webex_message_id
            )
        )).scalar() or 0

        # Get first reply timestamp if exists
        first_reply = (await db.execute(
            select(WebexMessage.created_at)
            .where(WebexMessage.parent_message_id == msg.webex_message_id)
            .order_by(WebexMessage.created_at.asc())
            .limit(1)
        )).scalar_one_or_none()

        response_time_hours = None
        if first_reply:
            response_time_hours = round((first_reply - msg.created_at).total_seconds() / 3600, 2)

        # Extract PR info from text if available
        import re
        pr_match = re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", msg.text or "")
        pr_number = int(pr_match.group(1)) if pr_match else None

        # Extract author from "by [Author]" pattern
        author_match = re.search(r"by \[?([^\]]+)\]?(?:\s+is ready|\s*$)", msg.text or "")
        pr_author = author_match.group(1) if author_match else msg.person_id

        recent_reviews.append({
            "pr_number": pr_number,
            "message_preview": (msg.text or "")[:100] + "..." if msg.text and len(msg.text) > 100 else msg.text,
            "author": pr_author,
            "posted_at": msg.created_at.isoformat(),
            "reply_count": reply_count,
            "response_time_hours": response_time_hours,
            "acknowledged": reply_count > 0,
        })

    return {
        "summary": {
            "total_messages": total_messages,
            "linked_to_prs": linked_to_prs,
            "review_requests": review_requests,
            "thread_replies": thread_replies,
            "avg_response_time_hours": avg_response_hours,
        },
        "recent_reviews": recent_reviews,
    }


# ── Sprint-Level Metrics ─────────────────────────────────────────────


@router.get("/sprints")
async def sprint_metrics(
    db: AsyncSession = Depends(get_db),
):
    """Sprint-level metrics: velocity, completion rate, AI impact comparison."""
    # Get all sprints with their issues
    sprints_result = await db.execute(
        select(Sprint).order_by(Sprint.start_date.desc()).limit(10)
    )
    sprints = sprints_result.scalars().all()

    sprint_data = []
    for sprint in sprints:
        # Get issues in this sprint
        issues_result = await db.execute(
            select(Issue).where(Issue.sprint_id == sprint.id)
        )
        issues = issues_result.scalars().all()

        total_issues = len(issues)
        done_issues = sum(1 for i in issues if i.status.lower() in DONE_STATUSES)

        # Velocity: sum of story points for done issues
        velocity = sum(i.story_points or 0 for i in issues if i.status.lower() in DONE_STATUSES)
        committed_points = sum(i.story_points or 0 for i in issues)

        # Completion rate
        completion_rate = round(done_issues / total_issues * 100, 1) if total_issues > 0 else 0

        # AI vs Non-AI velocity breakdown
        ai_velocity = 0
        non_ai_velocity = 0

        for issue in issues:
            if issue.status.lower() not in DONE_STATUSES:
                continue
            points = issue.story_points or 0

            # Check if AI-assisted via cycle metrics
            metrics_result = await db.execute(
                select(IssueCycleMetrics).where(IssueCycleMetrics.issue_id == issue.id)
            )
            metrics = metrics_result.scalar_one_or_none()

            if metrics and metrics.is_ai_assisted:
                ai_velocity += points
            else:
                non_ai_velocity += points

        sprint_data.append({
            "sprint_id": sprint.jira_sprint_id,
            "name": sprint.name,
            "state": sprint.state,
            "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
            "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
            "total_issues": total_issues,
            "done_issues": done_issues,
            "completion_rate": completion_rate,
            "velocity": velocity,
            "committed_points": committed_points,
            "ai_velocity": ai_velocity,
            "non_ai_velocity": non_ai_velocity,
            "ai_velocity_pct": round(ai_velocity / velocity * 100, 1) if velocity > 0 else 0,
        })

    # Aggregated stats across recent sprints
    total_velocity = sum(s["velocity"] for s in sprint_data)
    total_ai_velocity = sum(s["ai_velocity"] for s in sprint_data)
    avg_completion = sum(s["completion_rate"] for s in sprint_data) / len(sprint_data) if sprint_data else 0

    return {
        "summary": {
            "sprints_analyzed": len(sprint_data),
            "total_velocity": total_velocity,
            "avg_completion_rate": round(avg_completion, 1),
            "ai_velocity_total": total_ai_velocity,
            "ai_velocity_pct": round(total_ai_velocity / total_velocity * 100, 1) if total_velocity > 0 else 0,
        },
        "sprints": sprint_data,
    }


@router.get("/team-metrics")
async def team_metrics(
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Aggregated team-level metrics with AI impact analysis."""
    date_conds = _date_filter(Issue.created_at, start_date, end_date)

    # Review pickup time: avg time from PR opened to first review
    pr_date_conds = _date_filter(PullRequest.opened_at, start_date, end_date)
    q = select(PullRequest).where(
        PullRequest.first_review_at.isnot(None),
        PullRequest.opened_at.isnot(None),
    )
    if pr_date_conds:
        q = q.where(and_(*pr_date_conds))
    prs_result = await db.execute(q)
    prs = prs_result.scalars().all()

    pickup_times = []
    for pr in prs:
        delta = (pr.first_review_at - pr.opened_at).total_seconds() / 3600
        pickup_times.append(delta)
    avg_pickup_time = round(sum(pickup_times) / len(pickup_times), 2) if pickup_times else None

    # Rework rate: PRs with changes_requested / total reviewed PRs
    total_reviewed = len(prs)
    prs_with_changes = 0
    for pr in prs:
        comments_result = await db.execute(
            select(func.count(ReviewComment.id)).where(
                ReviewComment.pull_request_id == pr.id,
                ReviewComment.state == "changes_requested",
            )
        )
        if (comments_result.scalar() or 0) > 0:
            prs_with_changes += 1
    rework_rate = round(prs_with_changes / total_reviewed * 100, 1) if total_reviewed > 0 else 0

    # AI vs non-AI cycle time comparison
    ai_cycle_result = await db.execute(
        select(func.avg(IssueCycleMetrics.total_cycle_time_hours)).where(
            IssueCycleMetrics.is_ai_assisted == True  # noqa: E712
        )
    )
    non_ai_cycle_result = await db.execute(
        select(func.avg(IssueCycleMetrics.total_cycle_time_hours)).where(
            IssueCycleMetrics.is_ai_assisted == False  # noqa: E712
        )
    )
    avg_ai_cycle = ai_cycle_result.scalar()
    avg_non_ai_cycle = non_ai_cycle_result.scalar()

    # AI coding time savings
    ai_coding_result = await db.execute(
        select(func.avg(IssueCycleMetrics.coding_time_hours)).where(
            IssueCycleMetrics.is_ai_assisted == True  # noqa: E712
        )
    )
    non_ai_coding_result = await db.execute(
        select(func.avg(IssueCycleMetrics.coding_time_hours)).where(
            IssueCycleMetrics.is_ai_assisted == False  # noqa: E712
        )
    )
    avg_ai_coding = ai_coding_result.scalar()
    avg_non_ai_coding = non_ai_coding_result.scalar()

    coding_time_saved = None
    if avg_ai_coding and avg_non_ai_coding:
        coding_time_saved = round(avg_non_ai_coding - avg_ai_coding, 1)

    # Webex response time average
    webex_response_result = await db.execute(
        select(func.avg(IssueCycleMetrics.webex_response_time_hours)).where(
            IssueCycleMetrics.webex_response_time_hours.isnot(None)
        )
    )
    avg_webex_response = webex_response_result.scalar()

    return {
        "review_metrics": {
            "avg_pickup_time_hours": avg_pickup_time,
            "rework_rate_pct": rework_rate,
            "total_prs_reviewed": total_reviewed,
            "prs_needing_changes": prs_with_changes,
        },
        "ai_productivity": {
            "avg_ai_cycle_time_hours": round(avg_ai_cycle, 1) if avg_ai_cycle else None,
            "avg_non_ai_cycle_time_hours": round(avg_non_ai_cycle, 1) if avg_non_ai_cycle else None,
            "cycle_time_diff_hours": round(avg_non_ai_cycle - avg_ai_cycle, 1) if avg_ai_cycle and avg_non_ai_cycle else None,
            "avg_ai_coding_time_hours": round(avg_ai_coding, 1) if avg_ai_coding else None,
            "avg_non_ai_coding_time_hours": round(avg_non_ai_coding, 1) if avg_non_ai_coding else None,
            "coding_time_saved_hours": coding_time_saved,
        },
        "communication": {
            "avg_webex_response_time_hours": round(avg_webex_response, 2) if avg_webex_response else None,
        },
    }

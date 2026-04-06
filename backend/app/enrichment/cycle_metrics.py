"""
B8: IssueCycleMetrics Computation Engine

For each issue, computes coding time, review time, waiting time, total cycle time,
AI assistance flags, review rounds, and comment densities. Recomputes on any
relevant event (transition, PR merge, review).
"""
import json
import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AIAttribution,
    Commit,
    Issue,
    IssueCycleMetrics,
    IssueTransition,
    PullRequest,
    ReviewComment,
)

logger = logging.getLogger(__name__)


async def compute_for_issue(db: AsyncSession, issue_id: int) -> IssueCycleMetrics | None:
    """Compute or update cycle metrics for a single issue."""
    issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = issue_result.scalar_one_or_none()
    if not issue:
        return None

    # Get linked PRs
    prs_result = await db.execute(
        select(PullRequest).where(PullRequest.issue_id == issue_id)
    )
    prs = prs_result.scalars().all()

    # Get transitions
    transitions_result = await db.execute(
        select(IssueTransition)
        .where(IssueTransition.issue_id == issue_id)
        .order_by(IssueTransition.transitioned_at)
    )
    transitions = transitions_result.scalars().all()

    # Find "In Progress" timestamp from transitions
    in_progress_at = None
    for t in transitions:
        if t.to_status.lower() in ("in progress", "in development", "in review"):
            in_progress_at = t.transitioned_at
            break

    # Compute sub-stage times
    coding_time_hours = None
    review_time_hours = None
    waiting_time_hours = None
    total_cycle_time_hours = None

    if prs:
        first_pr_opened = min(pr.opened_at for pr in prs)

        # Coding Time: First PR Created - Issue "In Progress"
        if in_progress_at and first_pr_opened:
            coding_time_hours = _hours_between(in_progress_at, first_pr_opened)

        # Review Time: PR Approved - First Review Requested (or first review)
        merged_prs = [pr for pr in prs if pr.merged_at]
        if merged_prs:
            review_times = []
            for pr in merged_prs:
                review_start = pr.first_review_requested_at or pr.first_review_at
                review_end = pr.approved_at or pr.merged_at
                if review_start and review_end:
                    review_times.append(_hours_between(review_start, review_end))
            if review_times:
                review_time_hours = sum(review_times) / len(review_times)

    # Total Cycle Time: Resolved - In Progress (or Created)
    start = in_progress_at or issue.created_at
    end = issue.resolved_at
    if start and end:
        total_cycle_time_hours = _hours_between(start, end)

    # Waiting Time: Total - Coding - Review (derived)
    if total_cycle_time_hours is not None:
        known_time = (coding_time_hours or 0) + (review_time_hours or 0)
        waiting_time_hours = max(0, total_cycle_time_hours - known_time)

    # AI assistance: check if any linked PR has AI attributions
    is_ai_assisted = False
    ai_percentages = []
    for pr in prs:
        if pr.ai_percentage and pr.ai_percentage > 0:
            is_ai_assisted = True
            ai_percentages.append(pr.ai_percentage)
        else:
            # Check via commits -> attributions
            commits_result = await db.execute(
                select(Commit).where(Commit.pull_request_id == pr.id)
            )
            commit_ids = [c.id for c in commits_result.scalars().all()]
            if commit_ids:
                attr_count = await db.execute(
                    select(func.count(AIAttribution.id)).where(
                        AIAttribution.commit_id.in_(commit_ids)
                    )
                )
                if attr_count.scalar() > 0:
                    is_ai_assisted = True

    ai_percentage = sum(ai_percentages) / len(ai_percentages) if ai_percentages else None

    # Review rounds: count of "changes_requested" reviews across all PRs
    review_rounds = 0
    ai_comment_count = 0
    human_comment_count = 0
    total_lines = 0

    for pr in prs:
        comments_result = await db.execute(
            select(ReviewComment).where(ReviewComment.pull_request_id == pr.id)
        )
        comments = comments_result.scalars().all()

        changes_requested = sum(1 for c in comments if c.state == "changes_requested")
        review_rounds += changes_requested

        for c in comments:
            if c.is_on_ai_code:
                ai_comment_count += 1
            elif c.is_on_ai_code is False:
                human_comment_count += 1

        total_lines += (pr.additions or 0)

    ai_comment_density = (ai_comment_count / total_lines * 1000) if total_lines > 0 else None
    human_comment_density = (human_comment_count / total_lines * 1000) if total_lines > 0 else None

    # git-ai stats aggregation across all commits in linked PRs
    all_commits = []
    for pr in prs:
        commits_result = await db.execute(
            select(Commit).where(Commit.pull_request_id == pr.id)
        )
        all_commits.extend(commits_result.scalars().all())

    total_ai_accepted = sum(c.ai_accepted or 0 for c in all_commits)
    total_mixed = sum(c.mixed_additions or 0 for c in all_commits)
    total_ai_code = total_ai_accepted + total_mixed
    ai_accepted_ratio = (
        round(total_ai_accepted / total_ai_code * 100, 1) if total_ai_code > 0 else None
    )

    total_time_waiting = sum(c.time_waiting_for_ai_secs or 0 for c in all_commits)
    total_time_waiting_for_ai_secs = total_time_waiting if total_time_waiting > 0 else None

    tool_counts: Counter[str] = Counter()
    for c in all_commits:
        if c.tool_model_breakdown:
            try:
                breakdown = json.loads(c.tool_model_breakdown)
                for entry in breakdown:
                    tool = entry.get("tool", "unknown")
                    tool_counts[tool] += entry.get("additions", 0)
            except (json.JSONDecodeError, TypeError):
                pass
    primary_tool = tool_counts.most_common(1)[0][0] if tool_counts else None

    # Upsert IssueCycleMetrics
    result = await db.execute(
        select(IssueCycleMetrics).where(IssueCycleMetrics.issue_id == issue_id)
    )
    metrics = result.scalar_one_or_none()

    if not metrics:
        metrics = IssueCycleMetrics(issue_id=issue_id)
        db.add(metrics)

    metrics.coding_time_hours = coding_time_hours
    metrics.review_time_hours = review_time_hours
    metrics.waiting_time_hours = waiting_time_hours
    metrics.total_cycle_time_hours = total_cycle_time_hours
    metrics.is_ai_assisted = is_ai_assisted
    metrics.ai_percentage = ai_percentage
    metrics.review_rounds = review_rounds
    metrics.ai_accepted_ratio = ai_accepted_ratio
    metrics.total_time_waiting_for_ai_secs = total_time_waiting_for_ai_secs
    metrics.primary_tool = primary_tool
    metrics.ai_comment_density = ai_comment_density
    metrics.human_comment_density = human_comment_density
    metrics.computed_at = datetime.now(timezone.utc)

    await db.flush()
    logger.info("Computed cycle metrics for issue %s (id=%d)", issue.jira_key, issue_id)
    return metrics


async def recompute_all(db: AsyncSession) -> int:
    """Recompute cycle metrics for all issues that have linked PRs."""
    result = await db.execute(
        select(Issue.id).join(PullRequest, PullRequest.issue_id == Issue.id).distinct()
    )
    issue_ids = [row[0] for row in result.all()]
    count = 0
    for issue_id in issue_ids:
        m = await compute_for_issue(db, issue_id)
        if m:
            count += 1
    return count


def _hours_between(start: datetime, end: datetime) -> float:
    """Calculate hours between two datetimes."""
    delta = end - start
    return max(0, delta.total_seconds() / 3600)

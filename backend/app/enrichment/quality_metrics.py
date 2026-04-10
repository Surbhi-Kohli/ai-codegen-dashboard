"""
B9: AIQualityMetrics Computation Engine

For each merged PR with AI code, computes quality signals:
- Unmodified AI ratio (copy-paste indicator)
- AI review blind acceptance rate
- Follow-up fixes within 24h
- Test coverage on AI code
- Revert and defect linkage flags
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AIAttribution,
    AIQualityMetrics,
    Commit,
    Issue,
    PullRequest,
    ReviewComment,
)

logger = logging.getLogger(__name__)

# Paths that indicate test files
TEST_PATH_PATTERNS = ("test/", "tests/", "utest/", "utest_", "itest/", "itest_", "etest/", "spec/")


async def compute_for_pr(db: AsyncSession, pr_id: int) -> AIQualityMetrics | None:
    """Compute or update AI quality metrics for a single PR."""
    pr_result = await db.execute(select(PullRequest).where(PullRequest.id == pr_id))
    pr = pr_result.scalar_one_or_none()
    if not pr:
        return None

    # Get commits and AI attributions
    commits_result = await db.execute(
        select(Commit).where(Commit.pull_request_id == pr_id)
    )
    commits = commits_result.scalars().all()
    commit_ids = [c.id for c in commits]

    if not commit_ids:
        return None

    attr_result = await db.execute(
        select(AIAttribution).where(AIAttribution.commit_id.in_(commit_ids))
    )
    attributions = attr_result.scalars().all()

    if not attributions:
        return None  # No AI code in this PR — skip

    # ── Unmodified AI ratio (from git-ai stats) ────────────────────
    # ai_accepted = lines AI wrote that were committed as-is
    # mixed_additions = lines AI wrote that the human then edited
    total_ai_accepted = sum(c.ai_accepted or 0 for c in commits)
    total_mixed = sum(c.mixed_additions or 0 for c in commits)
    total_ai_code = total_ai_accepted + total_mixed
    ai_lines_unchanged = total_ai_accepted
    ai_lines_modified = total_mixed
    unmodified_ai_ratio = (
        round(total_ai_accepted / total_ai_code * 100, 1) if total_ai_code > 0 else None
    )

    # Total time waiting for AI across all commits in this PR
    total_wait_secs = sum(c.time_waiting_for_ai_secs or 0 for c in commits)

    # ── AI review blind acceptance ───────────────────────────────────
    comments_result = await db.execute(
        select(ReviewComment).where(
            ReviewComment.pull_request_id == pr_id,
            ReviewComment.is_bot == True,  # noqa: E712
        )
    )
    bot_comments = comments_result.scalars().all()

    ai_review_total_threads = len(bot_comments)
    ai_review_blind_accepts = 0

    for comment in bot_comments:
        resolved = comment.resolved_at
        # Fallback: if never explicitly resolved but PR is merged,
        # the developer effectively dismissed the comment by merging.
        if resolved is None and pr.merged_at:
            resolved = pr.merged_at

        if resolved and comment.created_at:
            resolution_time = (resolved - comment.created_at).total_seconds()
            if resolution_time < 120:  # resolved in < 2 minutes
                ai_review_blind_accepts += 1

    # ── Follow-up fixes within 24h ───────────────────────────────────
    followup_fixes_24h = 0
    if pr.merged_at:
        cutoff = pr.merged_at + timedelta(hours=24)
        # Find commits after merge that touch the same files
        ai_files = {a.file_path for a in attributions}

        # Look for later commits in the same repo that modify AI-attributed files
        # This is a simplified check — full implementation would inspect diffs
        later_commits_result = await db.execute(
            select(Commit).where(
                Commit.committed_at > pr.merged_at,
                Commit.committed_at <= cutoff,
            )
        )
        later_commits = later_commits_result.scalars().all()
        # Count commits whose messages reference the PR or touch similar files
        for c in later_commits:
            if f"#{pr.number}" in c.message or "fix" in c.message.lower():
                followup_fixes_24h += 1

    # ── Test coverage on AI code ─────────────────────────────────────
    # Check if any files in the PR diff are test files
    all_comment_files = set()
    all_comments_result = await db.execute(
        select(ReviewComment.file_path)
        .where(ReviewComment.pull_request_id == pr_id)
        .distinct()
    )
    all_comment_files = {row[0] for row in all_comments_result.all() if row[0]}

    # Heuristic: count test-related files from AI attribution file paths
    ai_file_paths = {a.file_path for a in attributions}
    test_lines_added = 0
    has_tests_for_ai_code = False

    for fp in ai_file_paths:
        if any(pattern in fp.lower() for pattern in TEST_PATH_PATTERNS):
            has_tests_for_ai_code = True
            # Estimate test lines from attributions in test files
            for a in attributions:
                if a.file_path == fp:
                    test_lines_added += a.ai_lines_end - a.ai_lines_start + 1

    # Also check non-AI test files in the PR (from PR additions metadata)
    # Full implementation would parse the PR diff file list

    # ── Revert detection ─────────────────────────────────────────────
    reverted_within_7d = False
    ai_lines_removed_ratio = 0.0
    if pr.merged_at:
        # Fast path: explicit revert via commit message
        revert_cutoff = pr.merged_at + timedelta(days=7)
        revert_result = await db.execute(
            select(Commit).where(
                Commit.committed_at > pr.merged_at,
                Commit.committed_at <= revert_cutoff,
                Commit.message.ilike(f"%revert%#{pr.number}%"),
            )
        )
        if revert_result.scalars().first():
            reverted_within_7d = True
            ai_lines_removed_ratio = 1.0
        else:
            # Line-level detection: check if AI-attributed lines were removed
            from app.enrichment.revert_detector import detect_ai_line_removal
            reverted_within_7d, ai_lines_removed_ratio = await detect_ai_line_removal(
                db, pr, attributions
            )

    # ── Defect linkage ───────────────────────────────────────────────
    defect_linked = False
    if pr.issue_id:
        # Check if any bug issue is linked to the same code
        # Simplified: check if the linked issue is a Bug type
        issue_result = await db.execute(
            select(Issue).where(Issue.id == pr.issue_id)
        )
        issue = issue_result.scalar_one_or_none()
        if issue and issue.issue_type.lower() == "bug":
            defect_linked = True

    # ── Upsert AIQualityMetrics ──────────────────────────────────────
    result = await db.execute(
        select(AIQualityMetrics).where(AIQualityMetrics.pr_id == pr_id)
    )
    metrics = result.scalar_one_or_none()

    if not metrics:
        metrics = AIQualityMetrics(pr_id=pr_id)
        db.add(metrics)

    metrics.ai_lines_unchanged = ai_lines_unchanged
    metrics.ai_lines_modified = ai_lines_modified
    metrics.unmodified_ai_ratio = unmodified_ai_ratio
    metrics.ai_review_blind_accepts = ai_review_blind_accepts
    metrics.ai_review_total_threads = ai_review_total_threads
    metrics.followup_fixes_24h = followup_fixes_24h
    metrics.test_lines_added = test_lines_added
    metrics.has_tests_for_ai_code = has_tests_for_ai_code
    metrics.total_time_waiting_for_ai_secs = total_wait_secs if total_wait_secs > 0 else None
    metrics.reverted_within_7d = reverted_within_7d
    metrics.ai_lines_removed_ratio = ai_lines_removed_ratio
    metrics.defect_linked = defect_linked
    metrics.computed_at = datetime.now(timezone.utc)

    await db.flush()
    logger.info("Computed quality metrics for PR #%d (id=%d)", pr.number, pr_id)
    return metrics


async def recompute_all(db: AsyncSession) -> int:
    """Recompute quality metrics for all PRs with commits."""
    result = await db.execute(
        select(PullRequest.id)
        .join(Commit, Commit.pull_request_id == PullRequest.id)
        .distinct()
    )
    pr_ids = [row[0] for row in result.all()]
    count = 0
    for pr_id in pr_ids:
        m = await compute_for_pr(db, pr_id)
        if m:
            count += 1
    return count

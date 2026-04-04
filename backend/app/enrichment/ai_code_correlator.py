"""
B7: Review Comment ↔ AI Code Correlator

For each review comment, checks if its file_path + line_number falls within
any AIAttribution line range for that PR's commits. Tags the comment as
"on AI code" or "on human code".
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIAttribution, Commit, PullRequest, ReviewComment

logger = logging.getLogger(__name__)


async def correlate_comments_for_pr(db: AsyncSession, pr_id: int) -> int:
    """Tag all review comments on a PR as on_ai_code or not."""
    # Get all commits for this PR
    commits_result = await db.execute(
        select(Commit).where(Commit.pull_request_id == pr_id)
    )
    commits = commits_result.scalars().all()
    commit_ids = [c.id for c in commits]

    if not commit_ids:
        return 0

    # Get all AI attributions for those commits
    attr_result = await db.execute(
        select(AIAttribution).where(AIAttribution.commit_id.in_(commit_ids))
    )
    attributions = attr_result.scalars().all()

    # Build lookup: file_path -> list of (start, end) ranges
    ai_ranges: dict[str, list[tuple[int, int]]] = {}
    for attr in attributions:
        ai_ranges.setdefault(attr.file_path, []).append(
            (attr.ai_lines_start, attr.ai_lines_end)
        )

    # Get all review comments for this PR that haven't been tagged yet
    comments_result = await db.execute(
        select(ReviewComment).where(
            ReviewComment.pull_request_id == pr_id,
            ReviewComment.is_on_ai_code.is_(None),
        )
    )
    comments = comments_result.scalars().all()
    tagged_count = 0

    for comment in comments:
        if not comment.file_path or not comment.line_number:
            comment.is_on_ai_code = False
            tagged_count += 1
            continue

        ranges = ai_ranges.get(comment.file_path, [])
        comment.is_on_ai_code = any(
            start <= comment.line_number <= end for start, end in ranges
        )
        tagged_count += 1

    if tagged_count:
        await db.flush()

    logger.info("Tagged %d comments for PR id=%d (%d AI attributions)", tagged_count, pr_id, len(attributions))
    return tagged_count


async def correlate_all_untagged(db: AsyncSession) -> int:
    """Find all PRs with untagged comments and correlate them."""
    result = await db.execute(
        select(ReviewComment.pull_request_id)
        .where(ReviewComment.is_on_ai_code.is_(None))
        .distinct()
    )
    pr_ids = [row[0] for row in result.all()]
    total = 0
    for pr_id in pr_ids:
        total += await correlate_comments_for_pr(db, pr_id)
    return total

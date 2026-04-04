"""
B6: Issue ↔ PR Linker

Matches Jira issue keys in PR branch names or PR titles/bodies to link
PullRequest records to Issue records.
"""
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Issue, PullRequest

logger = logging.getLogger(__name__)

# Matches patterns like ZTAEX-123, ZTCE-456 in branch names or PR text
JIRA_KEY_PATTERN = re.compile(r"[A-Z][A-Z0-9]+-\d+")


async def link_unlinked_prs(db: AsyncSession) -> int:
    """Find PRs without an issue link and attempt to match them."""
    result = await db.execute(
        select(PullRequest).where(PullRequest.issue_id.is_(None))
    )
    unlinked_prs = result.scalars().all()
    linked_count = 0

    for pr in unlinked_prs:
        jira_key = _extract_jira_key(pr.head_branch, pr.title)
        if not jira_key:
            continue

        issue_result = await db.execute(
            select(Issue).where(Issue.jira_key == jira_key)
        )
        issue = issue_result.scalar_one_or_none()
        if issue:
            pr.issue_id = issue.id
            linked_count += 1
            logger.info("Linked PR #%d → %s", pr.number, jira_key)

    if linked_count:
        await db.flush()

    logger.info("Linked %d/%d unlinked PRs", linked_count, len(unlinked_prs))
    return linked_count


def _extract_jira_key(branch_name: str, pr_title: str) -> str | None:
    """Extract a Jira issue key from branch name first, then PR title."""
    # Try branch name first (most reliable: feature/ZTAEX-123-description)
    matches = JIRA_KEY_PATTERN.findall(branch_name)
    if matches:
        return matches[0]

    # Fall back to PR title
    matches = JIRA_KEY_PATTERN.findall(pr_title)
    if matches:
        return matches[0]

    return None

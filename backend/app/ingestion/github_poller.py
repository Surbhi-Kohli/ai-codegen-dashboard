"""
GitHub Poller - Fetches PRs, reviews, and commits from GitHub API.
Follows same pattern as jira_poller.py.

Polls configured repos every N minutes for:
- Pull requests (open, merged, closed)
- PR reviews and review comments
- Commits (to link with git-ai data)
"""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Commit, PullRequest, Repository, ReviewComment
from app.db.session import async_session

logger = logging.getLogger(__name__)

# Track last poll time per repo for incremental sync
_last_poll: dict[str, str] = {}


def _auth_header() -> dict[str, str]:
    """GitHub API authentication header."""
    if not settings.github_token:
        return {"Accept": "application/vnd.github.v3+json"}
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }


async def poll_all_repos() -> None:
    """Poll all configured GitHub repos."""
    for repo in settings.github_repo_list:
        full_name = f"{settings.github_org}/{repo}"
        try:
            await _poll_repo(full_name)
        except Exception:
            logger.exception("Failed to poll GitHub repo %s", full_name)


async def _poll_repo(full_name: str) -> None:
    """Poll a single GitHub repo for PRs and related data."""
    async with async_session() as db:
        # Get or create repository record
        repo = await _get_or_create_repo(db, full_name)

        # Fetch PRs (all states for now, can add incremental later)
        prs_data = await _fetch_pull_requests(full_name)

        for pr_data in prs_data:
            await _upsert_pull_request(db, repo.id, pr_data, full_name)

        await db.commit()
        logger.info("Polled %d PRs from %s", len(prs_data), full_name)


async def _get_or_create_repo(db: AsyncSession, full_name: str) -> Repository:
    """Get or create a repository record."""
    result = await db.execute(
        select(Repository).where(Repository.github_repo == full_name)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        # Extract project key from repo name if possible
        repo_name = full_name.split("/")[-1]
        project_key = repo_name.upper().replace("-", "")[:10]

        repo = Repository(
            github_repo=full_name,
            jira_project_key=project_key,
        )
        db.add(repo)
        await db.flush()
        logger.info("Created repository: %s", full_name)

    return repo


async def _fetch_pull_requests(full_name: str) -> list[dict]:
    """Fetch pull requests from GitHub API with pagination."""
    all_prs = []
    page = 1
    per_page = 100

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"https://api.github.com/repos/{full_name}/pulls",
                headers=_auth_header(),
                params={
                    "state": "all",  # open, closed, merged
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": per_page,
                    "page": page,
                },
            )

            if resp.status_code == 403:
                logger.warning("GitHub API rate limit hit for %s", full_name)
                break

            resp.raise_for_status()
            prs = resp.json()

            if not prs:
                break

            all_prs.extend(prs)
            page += 1

            # Limit to recent PRs for initial poll
            if len(all_prs) >= 200:
                break

    return all_prs


async def _upsert_pull_request(
    db: AsyncSession, repo_id: int, pr_data: dict, full_name: str
) -> None:
    """Create or update a pull request and fetch its reviews/commits."""
    pr_number = pr_data["number"]

    # Check if PR exists
    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo_id,
            PullRequest.number == pr_number,
        )
    )
    pr = result.scalar_one_or_none()

    is_new_pr = pr is None
    if not pr:
        pr = PullRequest(
            github_pr_id=pr_data["id"],
            number=pr_number,
            repository_id=repo_id,
        )
        db.add(pr)

    # Update PR fields
    pr.title = pr_data["title"]
    pr.author = pr_data["user"]["login"]
    pr.head_branch = pr_data["head"]["ref"]
    pr.base_branch = pr_data["base"]["ref"]
    pr.additions = pr_data.get("additions")
    pr.deletions = pr_data.get("deletions")

    # List API doesn't return additions/deletions; fetch individual PR if missing
    if pr.additions is None:
        detail = await _fetch_pr_detail(full_name, pr_number)
        if detail:
            pr.additions = detail.get("additions")
            pr.deletions = detail.get("deletions")

    # State handling
    if pr_data.get("merged_at"):
        pr.state = "merged"
        pr.merged_at = _parse_github_datetime(pr_data["merged_at"])
    elif pr_data["state"] == "closed":
        pr.state = "closed"
        pr.closed_at = _parse_github_datetime(pr_data["closed_at"])
    else:
        pr.state = "open"

    pr.opened_at = _parse_github_datetime(pr_data["created_at"])

    if pr_data.get("closed_at"):
        pr.closed_at = _parse_github_datetime(pr_data["closed_at"])

    await db.flush()

    # Fetch reviews for this PR
    await _fetch_and_store_reviews(db, pr.id, full_name, pr_number)

    # Fetch commits for this PR
    await _fetch_and_store_commits(db, pr.id, full_name, pr_number)

    # Compute ai_percentage from linked commits' git-ai data
    commit_rows = await db.execute(
        select(Commit.ai_additions, Commit.human_additions, Commit.mixed_additions)
        .where(Commit.pull_request_id == pr.id)
    )
    total_ai = 0
    total_all = 0
    for row in commit_rows.all():
        ai = row[0] or 0
        human = row[1] or 0
        mixed = row[2] or 0
        total_ai += ai + mixed
        total_all += ai + human + mixed
    if total_all > 0:
        pr.ai_percentage = round(total_ai / total_all * 100, 1)
        pr.ai_lines_added = total_ai

    await db.flush()

    if is_new_pr:
        try:
            from app.integrations.webex_notifier import notify_pr
            result = await notify_pr(db, pr.id)
            logger.info("Webex notify for PR #%d: %s", pr_number, result.get("status"))
        except Exception:
            logger.debug("Webex notification skipped or failed for PR #%d", pr_number, exc_info=True)


async def _fetch_pr_detail(full_name: str, pr_number: int) -> dict | None:
    """Fetch a single PR's full details (includes additions/deletions)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}/pulls/{pr_number}",
            headers=_auth_header(),
        )
        if resp.status_code == 200:
            return resp.json()
    return None


async def _fetch_and_store_reviews(
    db: AsyncSession, pr_id: int, full_name: str, pr_number: int
) -> None:
    """Fetch and store PR reviews."""
    async with httpx.AsyncClient(timeout=30) as client:
        # Fetch reviews
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/reviews",
            headers=_auth_header(),
        )

        if resp.status_code != 200:
            return

        reviews = resp.json()

        # Get PR to update timestamps
        result = await db.execute(select(PullRequest).where(PullRequest.id == pr_id))
        pr = result.scalar_one_or_none()
        if not pr:
            return

        for review in reviews:
            submitted_at = _parse_github_datetime(review["submitted_at"])

            # Track first review
            if pr.first_review_at is None or submitted_at < pr.first_review_at:
                pr.first_review_at = submitted_at

            # Track approval
            if review["state"] == "APPROVED":
                if pr.approved_at is None or submitted_at < pr.approved_at:
                    pr.approved_at = submitted_at

        # Fetch review comments
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/comments",
            headers=_auth_header(),
        )

        if resp.status_code != 200:
            return

        comments = resp.json()

        for comment in comments:
            # Check if comment exists
            existing = await db.execute(
                select(ReviewComment).where(
                    ReviewComment.github_comment_id == comment["id"]
                )
            )
            if existing.scalar_one_or_none():
                continue

            rc = ReviewComment(
                github_comment_id=comment["id"],
                pull_request_id=pr_id,
                author=comment["user"]["login"],
                body=comment.get("body", ""),
                file_path=comment.get("path"),
                line_number=comment.get("line") or comment.get("original_line"),
                is_bot=comment["user"].get("type") == "Bot",
                created_at=_parse_github_datetime(comment["created_at"]),
            )
            db.add(rc)


async def _fetch_and_store_commits(
    db: AsyncSession, pr_id: int, full_name: str, pr_number: int
) -> None:
    """Fetch and store commits for a PR."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/commits",
            headers=_auth_header(),
        )

        if resp.status_code != 200:
            return

        commits = resp.json()

        for commit_data in commits:
            sha = commit_data["sha"]

            # Check if commit exists
            result = await db.execute(select(Commit).where(Commit.sha == sha))
            commit = result.scalar_one_or_none()

            if not commit:
                commit = Commit(
                    sha=sha,
                    message=commit_data["commit"]["message"][:500],
                    author=commit_data["commit"]["author"]["name"],
                    committed_at=_parse_github_datetime(
                        commit_data["commit"]["author"]["date"]
                    ),
                )
                db.add(commit)

            # Link commit to PR
            commit.pull_request_id = pr_id

        await db.flush()


def _parse_github_datetime(dt_str: str | None) -> datetime | None:
    """Parse GitHub datetime strings (ISO 8601)."""
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)

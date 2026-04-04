import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Commit, PullRequest, Repository, ReviewComment
from app.db.session import get_db

router = APIRouter()


def _verify_signature(payload: bytes, signature: str | None) -> None:
    if not settings.github_webhook_secret:
        return  # skip verification in dev if no secret configured
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256")
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


async def _get_or_create_repo(db: AsyncSession, full_name: str) -> Repository:
    result = await db.execute(select(Repository).where(Repository.github_repo == full_name))
    repo = result.scalar_one_or_none()
    if not repo:
        repo = Repository(github_repo=full_name)
        db.add(repo)
        await db.flush()
    return repo


@router.post("/")
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    payload = await request.body()
    _verify_signature(payload, x_hub_signature_256)
    data = await request.json()

    if x_github_event == "pull_request":
        await _handle_pull_request(db, data)
    elif x_github_event == "pull_request_review":
        await _handle_pr_review(db, data)
    elif x_github_event == "pull_request_review_comment":
        await _handle_pr_review_comment(db, data)
    elif x_github_event == "push":
        await _handle_push(db, data)

    await db.commit()
    return {"status": "ok"}


async def _handle_pull_request(db: AsyncSession, data: dict) -> None:
    pr_data = data["pull_request"]
    repo = await _get_or_create_repo(db, data["repository"]["full_name"])

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.number == pr_data["number"],
        )
    )
    pr = result.scalar_one_or_none()

    if not pr:
        pr = PullRequest(
            github_pr_id=pr_data["id"],
            number=pr_data["number"],
            repository_id=repo.id,
        )
        db.add(pr)

    pr.title = pr_data["title"]
    pr.author = pr_data["user"]["login"]
    pr.state = "merged" if pr_data.get("merged") else pr_data["state"]
    pr.head_branch = pr_data["head"]["ref"]
    pr.base_branch = pr_data["base"]["ref"]
    pr.additions = pr_data.get("additions")
    pr.deletions = pr_data.get("deletions")
    pr.opened_at = datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00"))

    if pr_data.get("merged_at"):
        pr.merged_at = datetime.fromisoformat(pr_data["merged_at"].replace("Z", "+00:00"))
    if pr_data.get("closed_at"):
        pr.closed_at = datetime.fromisoformat(pr_data["closed_at"].replace("Z", "+00:00"))

    await db.flush()


async def _handle_pr_review(db: AsyncSession, data: dict) -> None:
    review = data["review"]
    pr_data = data["pull_request"]
    repo = await _get_or_create_repo(db, data["repository"]["full_name"])

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.number == pr_data["number"],
        )
    )
    pr = result.scalar_one_or_none()
    if not pr:
        return

    submitted_at = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))

    # Track first review timestamp
    if pr.first_review_at is None or submitted_at < pr.first_review_at:
        pr.first_review_at = submitted_at

    # Track approval timestamp
    if review["state"] == "approved" and (pr.approved_at is None or submitted_at < pr.approved_at):
        pr.approved_at = submitted_at

    await db.flush()


async def _handle_pr_review_comment(db: AsyncSession, data: dict) -> None:
    comment = data["comment"]
    pr_data = data["pull_request"]
    repo = await _get_or_create_repo(db, data["repository"]["full_name"])

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.number == pr_data["number"],
        )
    )
    pr = result.scalar_one_or_none()
    if not pr:
        return

    # Check if comment already exists
    existing = await db.execute(
        select(ReviewComment).where(ReviewComment.github_comment_id == comment["id"])
    )
    if existing.scalar_one_or_none():
        return

    is_bot = comment["user"].get("type") == "Bot"

    rc = ReviewComment(
        github_comment_id=comment["id"],
        pull_request_id=pr.id,
        author=comment["user"]["login"],
        body=comment.get("body", ""),
        file_path=comment.get("path"),
        line_number=comment.get("line") or comment.get("original_line"),
        is_bot=is_bot,
        state=data.get("action"),
        created_at=datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00")),
    )
    db.add(rc)
    await db.flush()


async def _handle_push(db: AsyncSession, data: dict) -> None:
    repo = await _get_or_create_repo(db, data["repository"]["full_name"])

    for commit_data in data.get("commits", []):
        existing = await db.execute(
            select(Commit).where(Commit.sha == commit_data["id"])
        )
        if existing.scalar_one_or_none():
            continue

        c = Commit(
            sha=commit_data["id"],
            message=commit_data.get("message", ""),
            author=commit_data.get("author", {}).get("username", "unknown"),
            committed_at=datetime.fromisoformat(
                commit_data["timestamp"].replace("Z", "+00:00")
            ),
        )
        db.add(c)

    await db.flush()

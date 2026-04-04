import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AIAttribution, Commit
from app.db.session import get_db

router = APIRouter()


def _verify_signature(payload: bytes, signature: str | None) -> None:
    if not settings.gitai_webhook_secret:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")
    expected = "sha256=" + hmac.new(
        settings.gitai_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/")
async def gitai_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gitai_signature: str | None = Header(None),
):
    """
    Receives AI attribution data from git-ai post-push hook.

    Expected payload format:
    {
        "commit_sha": "abc123...",
        "attributions": [
            {
                "file_path": "src/handler.py",
                "line_start": 10,
                "line_end": 45,
                "agent": "copilot",
                "model": "gpt-4",
                "confidence": 0.95
            },
            ...
        ]
    }
    """
    payload = await request.body()
    _verify_signature(payload, x_gitai_signature)
    data = await request.json()

    commit_sha = data["commit_sha"]
    attributions = data.get("attributions", [])

    # Find the commit
    result = await db.execute(select(Commit).where(Commit.sha == commit_sha))
    commit = result.scalar_one_or_none()

    if not commit:
        # Commit may not have been ingested yet via GitHub webhook.
        # Store a minimal commit record so attributions are not lost.
        commit = Commit(
            sha=commit_sha,
            message="(pending — ingested via git-ai before GitHub webhook)",
            author="unknown",
            committed_at=data.get("committed_at"),
        )
        db.add(commit)
        await db.flush()

    for attr in attributions:
        ai_attr = AIAttribution(
            commit_id=commit.id,
            file_path=attr["file_path"],
            ai_lines_start=attr["line_start"],
            ai_lines_end=attr["line_end"],
            agent=attr.get("agent", "unknown"),
            model=attr.get("model"),
            confidence=attr.get("confidence"),
            raw_note=str(attr),
        )
        db.add(ai_attr)

    await db.commit()
    return {"status": "ok", "attributions_stored": len(attributions)}


@router.post("/backfill")
async def gitai_backfill(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk backfill endpoint for historical git-ai data.

    Expected payload:
    {
        "commits": [
            {
                "commit_sha": "abc123...",
                "attributions": [...]
            },
            ...
        ]
    }
    """
    data = await request.json()
    total_stored = 0

    for commit_data in data.get("commits", []):
        commit_sha = commit_data["commit_sha"]

        result = await db.execute(select(Commit).where(Commit.sha == commit_sha))
        commit = result.scalar_one_or_none()

        if not commit:
            commit = Commit(
                sha=commit_sha,
                message="(backfill — ingested via git-ai)",
                author="unknown",
                committed_at=commit_data.get("committed_at"),
            )
            db.add(commit)
            await db.flush()

        for attr in commit_data.get("attributions", []):
            ai_attr = AIAttribution(
                commit_id=commit.id,
                file_path=attr["file_path"],
                ai_lines_start=attr["line_start"],
                ai_lines_end=attr["line_end"],
                agent=attr.get("agent", "unknown"),
                model=attr.get("model"),
                confidence=attr.get("confidence"),
                raw_note=str(attr),
            )
            db.add(ai_attr)
            total_stored += 1

    await db.commit()
    return {"status": "ok", "attributions_stored": total_stored}

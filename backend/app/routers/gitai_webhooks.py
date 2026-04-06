"""
git-ai webhook and backfill endpoints.

Accepts two payload formats:
1. Real git-ai format (notes-based with prompt_id keys and nested ranges)
2. Simplified format (flat attributions list — kept for backward compat)

Also provides a /backfill endpoint for bulk historical ingestion.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

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


async def _get_or_create_commit(
    db: AsyncSession, sha: str, committed_at: str | None = None
) -> Commit:
    result = await db.execute(select(Commit).where(Commit.sha == sha))
    commit = result.scalar_one_or_none()
    if commit:
        return commit

    ts = datetime.now(timezone.utc)
    if committed_at:
        try:
            ts = datetime.fromisoformat(committed_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    commit = Commit(
        sha=sha,
        message="(pending — ingested via git-ai before GitHub webhook)",
        author="unknown",
        committed_at=ts,
    )
    db.add(commit)
    await db.flush()
    return commit


def _is_notes_format(data: dict) -> bool:
    """Detect whether payload uses real git-ai notes format vs simplified."""
    return "notes" in data or "stats" in data


async def _ingest_notes_format(db: AsyncSession, data: dict) -> int:
    """
    Ingest real git-ai format:
    {
      "commit_sha": "abc123",
      "stats": {
        "human_additions": 45, "ai_additions": 120, "mixed_additions": 15,
        "ai_accepted": 105, "total_ai_additions": 135, "total_ai_deletions": 8,
        "time_waiting_for_ai": 42,
        "tool_model_breakdown": [...]
      },
      "notes": {
        "<prompt_id>": {
          "agent_id": {"tool": "cursor", "model": "claude-sonnet-4-20250514"},
          "human_author": "aparey",
          "messages_url": "https://...",
          "ranges": {"src/handler.py": [[10, 45], [80, 95]]}
        }
      }
    }
    """
    sha = data["commit_sha"]
    commit = await _get_or_create_commit(db, sha, data.get("committed_at"))

    stats = data.get("stats", {})
    if stats:
        commit.human_additions = stats.get("human_additions")
        commit.ai_additions = stats.get("ai_additions")
        commit.mixed_additions = stats.get("mixed_additions")
        commit.ai_accepted = stats.get("ai_accepted")
        commit.total_ai_additions = stats.get("total_ai_additions")
        commit.total_ai_deletions = stats.get("total_ai_deletions")
        commit.time_waiting_for_ai_secs = stats.get("time_waiting_for_ai")
        breakdown = stats.get("tool_model_breakdown")
        if breakdown:
            commit.tool_model_breakdown = json.dumps(breakdown)

    attr_count = 0
    notes = data.get("notes", {})
    for prompt_id, prompt_data in notes.items():
        agent_id = prompt_data.get("agent_id", {})
        agent = agent_id.get("tool", "unknown")
        model = agent_id.get("model")
        human_author = prompt_data.get("human_author")
        messages_url = prompt_data.get("messages_url")

        for file_path, line_ranges in prompt_data.get("ranges", {}).items():
            for lr in line_ranges:
                if len(lr) >= 2:
                    ai_attr = AIAttribution(
                        commit_id=commit.id,
                        file_path=file_path,
                        ai_lines_start=lr[0],
                        ai_lines_end=lr[1],
                        agent=agent,
                        model=model,
                        prompt_id=prompt_id,
                        human_author=human_author,
                        messages_url=messages_url,
                        raw_note=json.dumps(prompt_data),
                    )
                    db.add(ai_attr)
                    attr_count += 1

    await db.flush()
    return attr_count


async def _ingest_simple_format(db: AsyncSession, data: dict) -> int:
    """Backward-compatible simplified format."""
    sha = data["commit_sha"]
    commit = await _get_or_create_commit(db, sha, data.get("committed_at"))

    attr_count = 0
    for attr in data.get("attributions", []):
        ai_attr = AIAttribution(
            commit_id=commit.id,
            file_path=attr["file_path"],
            ai_lines_start=attr["line_start"],
            ai_lines_end=attr["line_end"],
            agent=attr.get("agent", "unknown"),
            model=attr.get("model"),
            raw_note=json.dumps(attr),
        )
        db.add(ai_attr)
        attr_count += 1

    await db.flush()
    return attr_count


@router.post("/")
async def gitai_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gitai_signature: str | None = Header(None),
):
    """Receives AI attribution data from git-ai post-push hook."""
    payload = await request.body()
    _verify_signature(payload, x_gitai_signature)
    data = await request.json()

    if _is_notes_format(data):
        count = await _ingest_notes_format(db, data)
    else:
        count = await _ingest_simple_format(db, data)

    await db.commit()
    return {"status": "ok", "attributions_stored": count}


@router.post("/backfill")
async def gitai_backfill(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk backfill endpoint for historical git-ai data.
    Accepts array of commits in either format.
    """
    data = await request.json()
    total_stored = 0

    for commit_data in data.get("commits", []):
        if _is_notes_format(commit_data):
            total_stored += await _ingest_notes_format(db, commit_data)
        else:
            total_stored += await _ingest_simple_format(db, commit_data)

    await db.commit()
    return {"status": "ok", "attributions_stored": total_stored}

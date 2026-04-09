"""
Webex notifier: posts per-PR AI attribution summaries to a Webex space.
Triggered automatically when a new PR is detected by the GitHub poller,
or manually via the /api/notify-pr/{pr_id} endpoint.
"""
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AIAttribution, Commit, PullRequest, Repository

logger = logging.getLogger(__name__)

WEBEX_API = "https://webexapis.com/v1/messages"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.webex_bot_token}",
        "Content-Type": "application/json",
    }


async def notify_pr(db: AsyncSession, pr_id: int) -> dict:
    """Build and send a Webex message summarizing AI attribution for a PR."""
    if not settings.webex_bot_token or not settings.webex_review_room_id:
        return {"status": "skipped", "reason": "Webex not configured"}

    pr = (await db.execute(
        select(PullRequest).where(PullRequest.id == pr_id)
    )).scalar_one_or_none()
    if not pr:
        return {"status": "error", "reason": f"PR id={pr_id} not found"}

    repo = (await db.execute(
        select(Repository).where(Repository.id == pr.repository_id)
    )).scalar_one_or_none()
    repo_name = repo.github_repo if repo else "unknown"

    commits = (await db.execute(
        select(Commit).where(Commit.pull_request_id == pr.id)
    )).scalars().all()

    total_ai = sum(c.ai_additions or 0 for c in commits)
    total_human = sum(c.human_additions or 0 for c in commits)
    total_accepted = sum(c.ai_accepted or 0 for c in commits)
    total_all = total_ai + total_human
    ai_pct = round(total_ai / total_all * 100, 1) if total_all > 0 else 0
    accept_pct = round(total_accepted / total_ai * 100, 1) if total_ai > 0 else 0

    models_used: set[str] = set()
    for c in commits:
        if c.tool_model_breakdown:
            import json
            try:
                tmb = json.loads(c.tool_model_breakdown)
                if isinstance(tmb, dict):
                    for k in tmb:
                        models_used.add(k.replace("::", " / "))
            except (json.JSONDecodeError, TypeError):
                pass

    commit_ids = [c.id for c in commits]
    attributions = []
    if commit_ids:
        attr_result = await db.execute(
            select(
                AIAttribution.file_path,
                AIAttribution.ai_lines_start,
                AIAttribution.ai_lines_end,
                AIAttribution.model,
            )
            .where(AIAttribution.commit_id.in_(commit_ids))
            .order_by(
                (AIAttribution.ai_lines_end - AIAttribution.ai_lines_start).desc()
            )
        )
        attributions = attr_result.all()

    file_summary: dict[str, int] = {}
    for fp, start, end, _ in attributions:
        file_summary[fp] = file_summary.get(fp, 0) + (end - start + 1)
    top_files = sorted(file_summary.items(), key=lambda x: x[1], reverse=True)[:6]

    pr_url = f"https://github.com/{repo_name}/pull/{pr.number}"

    md = _build_markdown(
        pr=pr,
        pr_url=pr_url,
        repo_name=repo_name,
        ai_pct=ai_pct,
        total_ai=total_ai,
        total_all=total_all,
        accept_pct=accept_pct,
        models_used=models_used,
        top_files=top_files,
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            WEBEX_API,
            headers=_headers(),
            json={
                "roomId": settings.webex_review_room_id,
                "markdown": md,
            },
        )

    if resp.status_code in (200, 201):
        logger.info("Webex notification sent for PR #%d", pr.number)
        return {"status": "sent", "pr_number": pr.number}
    else:
        logger.error("Webex send failed: %d %s", resp.status_code, resp.text[:200])
        return {"status": "error", "code": resp.status_code, "detail": resp.text[:200]}


def _build_markdown(
    pr: PullRequest,
    pr_url: str,
    repo_name: str,
    ai_pct: float,
    total_ai: int,
    total_all: int,
    accept_pct: float,
    models_used: set[str],
    top_files: list[tuple[str, int]],
) -> str:
    state_emoji = {"open": "🟢", "merged": "🟣", "closed": "🔴"}.get(pr.state, "⚪")

    lines = [
        f"### {state_emoji} PR #{pr.number} — {pr.title}",
        f"**Repo:** `{repo_name}` · **Author:** {pr.author} · **State:** {pr.state}",
        f"[View on GitHub]({pr_url})",
        "",
        "---",
        "",
        "**AI Code Attribution** (via git-ai)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| AI-generated lines | **{total_ai}** of {total_all} ({ai_pct}%) |",
        f"| Accepted as-is | **{accept_pct}%** |",
    ]

    if models_used:
        lines.append(f"| Models used | {', '.join(f'`{m}`' for m in sorted(models_used))} |")

    if pr.additions is not None:
        lines.append(f"| PR additions / deletions | +{pr.additions} / -{pr.deletions or 0} |")

    if top_files:
        lines.append("")
        lines.append("**Top AI-touched files:**")
        for fp, line_count in top_files:
            short = fp.split("/")[-1] if "/" in fp else fp
            lines.append(f"- `{fp}` — **{line_count}** AI lines")

    lines.append("")
    lines.append("---")
    lines.append(f"_Sent by AI Codegen Dashboard_")

    return "\n".join(lines)

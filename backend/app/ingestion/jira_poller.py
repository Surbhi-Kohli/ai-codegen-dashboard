import base64
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Issue, IssueTransition, Sprint, TimeLog
from app.db.session import async_session

logger = logging.getLogger(__name__)

# Track last poll time per project for incremental sync
_last_poll: dict[str, str] = {}


def _auth_header() -> dict[str, str]:
    creds = base64.b64encode(f"{settings.jira_email}:{settings.jira_api_token}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def poll_all_projects() -> None:
    for project_key in settings.jira_project_key_list:
        try:
            await _poll_project(project_key)
        except Exception:
            logger.exception("Failed to poll Jira project %s", project_key)


async def _poll_project(project_key: str) -> None:
    async with async_session() as db:
        issues_data = await _fetch_issues(project_key)
        for issue_data in issues_data:
            await _upsert_issue(db, issue_data)
        await db.commit()
        logger.info("Polled %d issues from %s", len(issues_data), project_key)


async def _fetch_issues(project_key: str) -> list[dict]:
    """Fetch issues from Jira REST API with pagination and incremental sync."""
    all_issues = []
    start_at = 0
    max_results = 50

    # Incremental: only fetch issues updated since last poll
    jql = f"project = {project_key}"
    last = _last_poll.get(project_key)
    if last:
        jql += f' AND updated >= "{last}"'
    jql += " ORDER BY updated ASC"

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"{settings.jira_base_url}/rest/api/3/search",
                headers=_auth_header(),
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "summary,issuetype,status,priority,assignee,created,"
                              "updated,resolutiondate,story_points,sprint",
                    "expand": "changelog",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            all_issues.extend(data.get("issues", []))

            total = data.get("total", 0)
            start_at += max_results
            if start_at >= total:
                break

    # Update last poll timestamp
    _last_poll[project_key] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return all_issues


async def _upsert_issue(db: AsyncSession, issue_data: dict) -> None:
    """Create or update an issue and its transitions from Jira changelog."""
    fields = issue_data["fields"]
    jira_key = issue_data["key"]
    jira_id = str(issue_data["id"])

    result = await db.execute(select(Issue).where(Issue.jira_key == jira_key))
    issue = result.scalar_one_or_none()

    if not issue:
        issue = Issue(jira_key=jira_key, jira_id=jira_id)
        db.add(issue)

    issue.issue_type = fields["issuetype"]["name"]
    issue.summary = fields.get("summary", "")
    issue.status = fields["status"]["name"]
    issue.priority = fields.get("priority", {}).get("name") if fields.get("priority") else None

    if fields.get("assignee"):
        issue.assignee_name = fields["assignee"].get("displayName")
        issue.assignee_account_id = fields["assignee"].get("accountId")

    issue.story_points = fields.get("story_points")
    issue.created_at = _parse_jira_datetime(fields["created"])
    issue.updated_at = _parse_jira_datetime(fields.get("updated")) if fields.get("updated") else None
    issue.resolved_at = _parse_jira_datetime(fields.get("resolutiondate")) if fields.get("resolutiondate") else None

    # Sprint linkage
    sprint_data = fields.get("sprint")
    if sprint_data:
        issue.sprint_id = await _upsert_sprint(db, sprint_data)

    await db.flush()

    # Process changelog for status transitions
    changelog = issue_data.get("changelog", {})
    for history in changelog.get("histories", []):
        for item in history.get("items", []):
            if item["field"] == "status":
                await _upsert_transition(
                    db,
                    issue_id=issue.id,
                    from_status=item.get("fromString"),
                    to_status=item.get("toString", ""),
                    transitioned_at=_parse_jira_datetime(history["created"]),
                    author_account_id=history.get("author", {}).get("accountId"),
                )

    await db.flush()


async def _upsert_sprint(db: AsyncSession, sprint_data: dict) -> int:
    """Create or update a sprint and return its DB id."""
    jira_sprint_id = sprint_data["id"]

    result = await db.execute(select(Sprint).where(Sprint.jira_sprint_id == jira_sprint_id))
    sprint = result.scalar_one_or_none()

    if not sprint:
        sprint = Sprint(jira_sprint_id=jira_sprint_id, name=sprint_data.get("name", ""))
        db.add(sprint)

    sprint.name = sprint_data.get("name", sprint.name)
    sprint.state = sprint_data.get("state")
    if sprint_data.get("startDate"):
        sprint.start_date = _parse_jira_datetime(sprint_data["startDate"])
    if sprint_data.get("endDate"):
        sprint.end_date = _parse_jira_datetime(sprint_data["endDate"])
    if sprint_data.get("completeDate"):
        sprint.complete_date = _parse_jira_datetime(sprint_data["completeDate"])

    await db.flush()
    return sprint.id


async def _upsert_transition(
    db: AsyncSession,
    issue_id: int,
    from_status: str | None,
    to_status: str,
    transitioned_at: datetime,
    author_account_id: str | None,
) -> None:
    """Insert a transition if it doesn't already exist (dedup by issue + timestamp + to_status)."""
    result = await db.execute(
        select(IssueTransition).where(
            IssueTransition.issue_id == issue_id,
            IssueTransition.to_status == to_status,
            IssueTransition.transitioned_at == transitioned_at,
        )
    )
    if result.scalar_one_or_none():
        return

    transition = IssueTransition(
        issue_id=issue_id,
        from_status=from_status,
        to_status=to_status,
        transitioned_at=transitioned_at,
        author_account_id=author_account_id,
    )
    db.add(transition)


def _parse_jira_datetime(dt_str: str) -> datetime:
    """Parse Jira datetime strings (ISO 8601 with timezone offset)."""
    if not dt_str:
        return datetime.now(timezone.utc)
    # Jira format: 2024-01-15T10:30:00.000+0530 or 2024-01-15T10:30:00.000Z
    dt_str = dt_str.replace("Z", "+00:00")
    # Handle +0530 format (no colon) — convert to +05:30
    if len(dt_str) > 5 and dt_str[-5] in "+-" and ":" not in dt_str[-5:]:
        dt_str = dt_str[:-2] + ":" + dt_str[-2:]
    return datetime.fromisoformat(dt_str)

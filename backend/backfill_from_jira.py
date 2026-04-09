"""
Backfill script: Inserts Jira data from JSON file into the dashboard database.
Usage: python backfill_from_jira.py jira_data.json
"""
import asyncio
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Base, Issue, IssueTransition, Repository, Sprint
from app.db.session import async_session, engine


def parse_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        # Handle various Jira datetime formats
        dt_str = dt_str.replace("Z", "+00:00")
        if "." in dt_str and "+" in dt_str:
            # Format: 2026-04-08T02:05:14.626-0700
            dt_str = dt_str.rsplit(".", 1)[0] + dt_str[-5:]
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return None


async def backfill_issues(data: dict) -> int:
    """Insert issues from Jira API response."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Create or get repository
        project_key = data["issues"]["nodes"][0]["fields"]["project"]["key"]
        project_name = data["issues"]["nodes"][0]["fields"]["project"]["name"]

        result = await db.execute(
            select(Repository).where(Repository.jira_project_key == project_key)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            repo = Repository(
                github_repo=f"duo-security/{project_key.lower()}",
                jira_project_key=project_key,
            )
            db.add(repo)
            await db.flush()
            print(f"Created repository: {project_key}")

        count = 0
        for node in data["issues"]["nodes"]:
            fields = node["fields"]
            jira_key = node["key"]
            jira_id = node["id"]

            # Check if issue exists
            existing = await db.execute(
                select(Issue).where(Issue.jira_key == jira_key)
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping {jira_key} (already exists)")
                continue

            assignee = fields.get("assignee")
            issue = Issue(
                jira_key=jira_key,
                jira_id=jira_id,
                issue_type=fields["issuetype"]["name"],
                summary=fields["summary"],
                status=fields["status"]["name"],
                priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
                assignee_name=assignee["displayName"] if assignee else None,
                assignee_account_id=assignee["accountId"] if assignee else None,
                story_points=fields.get("customfield_10004"),
                created_at=parse_datetime(fields["created"]),
                updated_at=parse_datetime(fields.get("updated")),
                resolved_at=parse_datetime(fields.get("resolutiondate")),
                repository_id=repo.id,
            )
            db.add(issue)
            count += 1
            print(f"  Added {jira_key}: {fields['summary'][:50]}...")

        await db.commit()
        return count


async def backfill_transitions(data: dict) -> int:
    """Insert issue transitions from changelog data."""
    async with async_session() as db:
        count = 0
        for item in data.get("transitions", []):
            jira_key = item["jira_key"]

            # Find the issue
            result = await db.execute(
                select(Issue).where(Issue.jira_key == jira_key)
            )
            issue = result.scalar_one_or_none()
            if not issue:
                print(f"  Issue {jira_key} not found, skipping transitions")
                continue

            for t in item.get("history", []):
                transition = IssueTransition(
                    issue_id=issue.id,
                    from_status=t.get("from_status"),
                    to_status=t["to_status"],
                    transitioned_at=parse_datetime(t["transitioned_at"]),
                    author_account_id=t.get("author_account_id"),
                )
                db.add(transition)
                count += 1

        await db.commit()
        return count


async def main():
    if len(sys.argv) < 2:
        print("Usage: python backfill_from_jira.py <jira_data.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    print("Backfilling issues...")
    issue_count = await backfill_issues(data)
    print(f"Inserted {issue_count} issues")

    if "transitions" in data:
        print("\nBackfilling transitions...")
        trans_count = await backfill_transitions(data)
        print(f"Inserted {trans_count} transitions")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())

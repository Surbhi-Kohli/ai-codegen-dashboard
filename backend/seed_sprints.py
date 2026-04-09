#!/usr/bin/env python3
"""Seed sprint data and link some issues to sprints."""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from sqlalchemy import select, update
from app.db.models import Base, Issue, Sprint
from app.db.session import async_session, engine


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Create sprints
        now = datetime.now(timezone.utc)
        sprints_data = [
            {
                "jira_sprint_id": 1001,
                "name": "Sprint 24.1",
                "state": "closed",
                "start_date": now - timedelta(days=28),
                "end_date": now - timedelta(days=14),
            },
            {
                "jira_sprint_id": 1002,
                "name": "Sprint 24.2",
                "state": "closed",
                "start_date": now - timedelta(days=14),
                "end_date": now,
            },
            {
                "jira_sprint_id": 1003,
                "name": "Sprint 24.3",
                "state": "active",
                "start_date": now,
                "end_date": now + timedelta(days=14),
            },
        ]

        sprint_ids = []
        for sd in sprints_data:
            # Check if exists
            existing = await db.execute(
                select(Sprint).where(Sprint.jira_sprint_id == sd["jira_sprint_id"])
            )
            sprint = existing.scalar_one_or_none()
            if not sprint:
                sprint = Sprint(**sd)
                db.add(sprint)
                await db.flush()
            sprint_ids.append(sprint.id)

        # Link issues to sprints
        issues_result = await db.execute(select(Issue).limit(20))
        issues = issues_result.scalars().all()

        for i, issue in enumerate(issues):
            # Distribute across sprints
            sprint_idx = i % len(sprint_ids)
            issue.sprint_id = sprint_ids[sprint_idx]

        await db.commit()
        print(f"Created {len(sprints_data)} sprints")
        print(f"Linked {len(issues)} issues to sprints")


if __name__ == "__main__":
    asyncio.run(main())

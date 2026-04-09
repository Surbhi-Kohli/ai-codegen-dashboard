"""
Seed realistic Jira issues + cycle metrics for the demo.
Links issues to the real PR and commits already in the database.
Run: python seed_jira_demo.py
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.db.models import (
    Base,
    Issue,
    IssueCycleMetrics,
    IssueTransition,
    PullRequest,
    Repository,
    Sprint,
)
from app.db.session import async_session, engine

NOW = datetime.now(timezone.utc)


SPRINT = {
    "jira_sprint_id": 9901,
    "name": "DEMO Sprint 24.15",
    "state": "active",
    "start_date": NOW - timedelta(days=10),
    "end_date": NOW + timedelta(days=4),
}

ISSUES = [
    {
        "jira_key": "DEMO-101",
        "jira_id": "900101",
        "issue_type": "Story",
        "summary": "Add login rate limiter to auth service",
        "status": "Code Review",
        "priority": "High",
        "assignee_name": "Anushka Parey",
        "created_at": NOW - timedelta(days=3, hours=6),
        "updated_at": NOW - timedelta(hours=2),
        "resolved_at": None,
        "story_points": 5,
        "is_ai_assisted": True,
        "link_to_pr": 1,
        "transitions": [
            ("Backlog", "To Do", -3, -5),
            ("To Do", "In Progress", -2, -8),
            ("In Progress", "Code Review", -0, -3),
        ],
        "coding_hours": 2.5,
        "review_hours": 1.8,
        "waiting_hours": 0.5,
    },
    {
        "jira_key": "DEMO-102",
        "jira_id": "900102",
        "issue_type": "Story",
        "summary": "Scaffold trustedpath-dummy-demo-service microservice",
        "status": "Done",
        "priority": "High",
        "assignee_name": "Anushka Parey",
        "created_at": NOW - timedelta(days=5),
        "updated_at": NOW - timedelta(days=2),
        "resolved_at": NOW - timedelta(days=2, hours=4),
        "story_points": 8,
        "is_ai_assisted": True,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "To Do", -5, 0),
            ("To Do", "In Progress", -4, -2),
            ("In Progress", "Code Review", -3, -1),
            ("Code Review", "Done", -2, -4),
        ],
        "coding_hours": 1.2,
        "review_hours": 0.8,
        "waiting_hours": 0.3,
    },
    {
        "jira_key": "DEMO-103",
        "jira_id": "900103",
        "issue_type": "Bug",
        "summary": "Fix session timeout not respecting idle config",
        "status": "Done",
        "priority": "Critical",
        "assignee_name": "Surbhi Kohli",
        "created_at": NOW - timedelta(days=7),
        "updated_at": NOW - timedelta(days=4),
        "resolved_at": NOW - timedelta(days=4, hours=6),
        "story_points": 3,
        "is_ai_assisted": False,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "In Progress", -6, -6),
            ("In Progress", "Code Review", -5, -2),
            ("Code Review", "Done", -4, -6),
        ],
        "coding_hours": 4.0,
        "review_hours": 2.5,
        "waiting_hours": 1.2,
    },
    {
        "jira_key": "DEMO-104",
        "jira_id": "900104",
        "issue_type": "Task",
        "summary": "Add health check and readiness probe endpoints",
        "status": "Done",
        "priority": "Medium",
        "assignee_name": "Anushka Parey",
        "created_at": NOW - timedelta(days=6),
        "updated_at": NOW - timedelta(days=3),
        "resolved_at": NOW - timedelta(days=3, hours=2),
        "story_points": 2,
        "is_ai_assisted": True,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "To Do", -6, 0),
            ("To Do", "In Progress", -5, 0),
            ("In Progress", "Code Review", -4, -1),
            ("Code Review", "Done", -3, -2),
        ],
        "coding_hours": 0.8,
        "review_hours": 0.5,
        "waiting_hours": 0.2,
    },
    {
        "jira_key": "DEMO-105",
        "jira_id": "900105",
        "issue_type": "Story",
        "summary": "Implement device trust verification flow",
        "status": "In Progress",
        "priority": "High",
        "assignee_name": "Surbhi Kohli",
        "created_at": NOW - timedelta(days=4),
        "updated_at": NOW - timedelta(hours=8),
        "resolved_at": None,
        "story_points": 8,
        "is_ai_assisted": False,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "To Do", -3, -6),
            ("To Do", "In Progress", -2, 0),
        ],
        "coding_hours": 6.0,
        "review_hours": None,
        "waiting_hours": 2.0,
    },
    {
        "jira_key": "DEMO-106",
        "jira_id": "900106",
        "issue_type": "Story",
        "summary": "Build AI codegen metrics dashboard frontend",
        "status": "Code Review",
        "priority": "High",
        "assignee_name": "Anushka Parey",
        "created_at": NOW - timedelta(days=4),
        "updated_at": NOW - timedelta(hours=1),
        "resolved_at": None,
        "story_points": 13,
        "is_ai_assisted": True,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "To Do", -4, 0),
            ("To Do", "In Progress", -3, 0),
            ("In Progress", "Code Review", -0, -2),
        ],
        "coding_hours": 3.5,
        "review_hours": 1.0,
        "waiting_hours": 0.5,
    },
    {
        "jira_key": "DEMO-107",
        "jira_id": "900107",
        "issue_type": "Bug",
        "summary": "Database connection pool exhaustion under load",
        "status": "Done",
        "priority": "Critical",
        "assignee_name": "Surbhi Kohli",
        "created_at": NOW - timedelta(days=8),
        "updated_at": NOW - timedelta(days=5),
        "resolved_at": NOW - timedelta(days=5),
        "story_points": 5,
        "is_ai_assisted": True,
        "link_to_pr": None,
        "transitions": [
            ("Backlog", "In Progress", -8, 0),
            ("In Progress", "Code Review", -6, -4),
            ("Code Review", "In Progress", -6, 0),
            ("In Progress", "Code Review", -5, -6),
            ("Code Review", "Done", -5, 0),
        ],
        "coding_hours": 5.5,
        "review_hours": 3.0,
        "waiting_hours": 1.5,
    },
    {
        "jira_key": "DEMO-108",
        "jira_id": "900108",
        "issue_type": "Task",
        "summary": "Set up CI pipeline for demo service",
        "status": "To Do",
        "priority": "Medium",
        "assignee_name": None,
        "created_at": NOW - timedelta(days=2),
        "updated_at": NOW - timedelta(days=2),
        "resolved_at": None,
        "story_points": 3,
        "is_ai_assisted": False,
        "link_to_pr": None,
        "transitions": [],
        "coding_hours": None,
        "review_hours": None,
        "waiting_hours": None,
    },
]


async def seed():
    async with async_session() as db:
        existing = (await db.execute(select(func.count(Issue.id)))).scalar()
        if existing and existing > 0:
            print(f"DB already has {existing} issues. Skipping seed to avoid duplicates.")
            print("Delete ai_dashboard.db and re-run extractors + this script for a fresh start.")
            return

        repo = (await db.execute(select(Repository).limit(1))).scalar_one_or_none()
        repo_id = repo.id if repo else None

        sprint = Sprint(**SPRINT)
        db.add(sprint)
        await db.flush()

        for iss_data in ISSUES:
            issue = Issue(
                jira_key=iss_data["jira_key"],
                jira_id=iss_data["jira_id"],
                issue_type=iss_data["issue_type"],
                summary=iss_data["summary"],
                status=iss_data["status"],
                priority=iss_data["priority"],
                assignee_name=iss_data.get("assignee_name"),
                story_points=iss_data.get("story_points"),
                created_at=iss_data["created_at"],
                updated_at=iss_data.get("updated_at"),
                resolved_at=iss_data.get("resolved_at"),
                repository_id=repo_id,
                sprint_id=sprint.id,
            )
            db.add(issue)
            await db.flush()

            for from_s, to_s, day_offset, hour_offset in iss_data["transitions"]:
                t = IssueTransition(
                    issue_id=issue.id,
                    from_status=from_s,
                    to_status=to_s,
                    transitioned_at=NOW + timedelta(days=day_offset, hours=hour_offset),
                )
                db.add(t)

            if iss_data.get("link_to_pr"):
                pr = (await db.execute(
                    select(PullRequest).where(PullRequest.id == iss_data["link_to_pr"])
                )).scalar_one_or_none()
                if pr:
                    pr.issue_id = issue.id

            coding = iss_data.get("coding_hours")
            review = iss_data.get("review_hours")
            waiting = iss_data.get("waiting_hours")
            total = sum(x for x in [coding, review, waiting] if x) if any([coding, review, waiting]) else None

            metrics = IssueCycleMetrics(
                issue_id=issue.id,
                coding_time_hours=coding,
                review_time_hours=review,
                waiting_time_hours=waiting,
                total_cycle_time_hours=total,
                is_ai_assisted=iss_data["is_ai_assisted"],
                ai_percentage=99.3 if iss_data["is_ai_assisted"] else 0,
                review_rounds=len([t for t in iss_data["transitions"] if t[1] == "Code Review"]),
                primary_tool="cursor" if iss_data["is_ai_assisted"] else None,
                computed_at=NOW,
            )
            db.add(metrics)

        await db.commit()
        final_count = (await db.execute(select(func.count(Issue.id)))).scalar()
        print(f"Seeded {final_count} issues with transitions and cycle metrics.")


if __name__ == "__main__":
    asyncio.run(seed())

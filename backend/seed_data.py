"""
Seed script: Inserts real Jira + GitHub data into the SQLite database.
Run with: python seed_data.py
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    AIAttribution,
    Base,
    Commit,
    Issue,
    IssueTransition,
    IssueCycleMetrics,
    PullRequest,
    Repository,
    ReviewComment,
)
from app.db.session import async_session, engine


# ── Real Jira issues from ZTAEX project ─────────────────────────────

JIRA_ISSUES = [
    {
        "jira_key": "ZTAEX-2353",
        "jira_id": "6666855",
        "issue_type": "Task",
        "summary": "AMR validation needs to be a full match and not a subset check",
        "status": "Code Review",
        "priority": "Low",
        "assignee_name": "Bryan Mason",
        "assignee_account_id": "712020:08434182-261b-45b8-a47d-53d2d83d3d7d",
        "created_at": "2026-03-26T09:29:23-07:00",
        "updated_at": "2026-04-03T12:03:48-07:00",
        "resolved_at": None,
    },
    {
        "jira_key": "ZTAEX-2358",
        "jira_id": "6674680",
        "issue_type": "Task",
        "summary": "Update test CODEOWNERS for adminserv adminapiserv and adminapi-evergreen",
        "status": "Done",
        "priority": "TBD",
        "assignee_name": "Luis Chang",
        "assignee_account_id": "712020:532953f3-75ad-4375-b04a-6666aecb6da3",
        "created_at": "2026-03-27T08:48:26-07:00",
        "updated_at": "2026-04-03T09:16:20-07:00",
        "resolved_at": "2026-04-03T09:16:20-07:00",
    },
    {
        "jira_key": "ZTAEX-2347",
        "jira_id": "6624383",
        "issue_type": "Bug",
        "summary": "pageSubtitle does not have proper maxWidth defined",
        "status": "Code Review",
        "priority": "TBD",
        "assignee_name": "Bohdan Sharko",
        "assignee_account_id": "712020:bc2f72b4-10b9-4683-9e82-ac804d602a9d",
        "created_at": "2026-03-18T11:48:46-07:00",
        "updated_at": "2026-04-03T07:52:12-07:00",
        "resolved_at": None,
    },
    {
        "jira_key": "ZTAEX-2356",
        "jira_id": "6674613",
        "issue_type": "Story",
        "summary": "[Sprint Goal] External Docs + Scaling Documentation",
        "status": "Backlog",
        "priority": "TBD",
        "assignee_name": "Pavlo Zherzherunov",
        "assignee_account_id": "712020:74d126bb-665f-498e-9d85-947468eb4fe7",
        "created_at": "2026-03-27T08:30:00-07:00",
        "updated_at": "2026-03-30T05:27:06-07:00",
        "resolved_at": None,
    },
    {
        "jira_key": "ZTAEX-2352",
        "jira_id": "6665893",
        "issue_type": "Task",
        "summary": "[SPIKE] Work breakdown for Admin Panel BreachDB",
        "status": "Backlog",
        "priority": "TBD",
        "assignee_name": "Pavlo Zherzherunov",
        "assignee_account_id": "712020:74d126bb-665f-498e-9d85-947468eb4fe7",
        "created_at": "2026-03-26T05:27:28-07:00",
        "updated_at": "2026-03-30T02:19:43-07:00",
        "resolved_at": None,
    },
    {
        "jira_key": "ZTAEX-298",
        "jira_id": "59487",
        "issue_type": "Story",
        "summary": "Refactor administrators handlers to commonalize code",
        "status": "Selected for Development",
        "priority": "Highest",
        "assignee_name": None,
        "assignee_account_id": None,
        "created_at": "2020-05-27T09:30:07-07:00",
        "updated_at": "2026-03-30T05:27:02-07:00",
        "resolved_at": None,
    },
    {
        "jira_key": "ZTAEX-310",
        "jira_id": "59499",
        "issue_type": "Story",
        "summary": "Clean up hardtoken stuff in administrator handlers after AdPro is GA",
        "status": "Selected for Development",
        "priority": "High",
        "assignee_name": None,
        "assignee_account_id": None,
        "created_at": "2020-05-28T13:29:26-07:00",
        "updated_at": "2026-03-30T05:26:45-07:00",
        "resolved_at": None,
    },
    # Additional resolved issues for richer metrics
    {
        "jira_key": "ZTAEX-2340",
        "jira_id": "6610001",
        "issue_type": "Task",
        "summary": "Migrate adminserv webpack config to rspack",
        "status": "Done",
        "priority": "Medium",
        "assignee_name": "Luis Chang",
        "assignee_account_id": "712020:532953f3-75ad-4375-b04a-6666aecb6da3",
        "created_at": "2026-03-10T10:00:00-07:00",
        "updated_at": "2026-03-20T14:30:00-07:00",
        "resolved_at": "2026-03-20T14:30:00-07:00",
    },
    {
        "jira_key": "ZTAEX-2335",
        "jira_id": "6600002",
        "issue_type": "Bug",
        "summary": "Admin panel login redirect loop on Safari",
        "status": "Done",
        "priority": "High",
        "assignee_name": "Bryan Mason",
        "assignee_account_id": "712020:08434182-261b-45b8-a47d-53d2d83d3d7d",
        "created_at": "2026-03-05T08:00:00-07:00",
        "updated_at": "2026-03-12T16:00:00-07:00",
        "resolved_at": "2026-03-12T16:00:00-07:00",
    },
    {
        "jira_key": "ZTAEX-2330",
        "jira_id": "6590003",
        "issue_type": "Story",
        "summary": "Add Duo Desktop health check endpoint for ZTNA posture",
        "status": "Done",
        "priority": "High",
        "assignee_name": "Bohdan Sharko",
        "assignee_account_id": "712020:bc2f72b4-10b9-4683-9e82-ac804d602a9d",
        "created_at": "2026-03-01T09:00:00-07:00",
        "updated_at": "2026-03-18T11:00:00-07:00",
        "resolved_at": "2026-03-18T11:00:00-07:00",
    },
    {
        "jira_key": "ZTAEX-2345",
        "jira_id": "6620004",
        "issue_type": "Task",
        "summary": "Implement session trust quarantine API v2",
        "status": "Done",
        "priority": "Medium",
        "assignee_name": "Bryan Mason",
        "assignee_account_id": "712020:08434182-261b-45b8-a47d-53d2d83d3d7d",
        "created_at": "2026-03-15T10:00:00-07:00",
        "updated_at": "2026-03-28T15:00:00-07:00",
        "resolved_at": "2026-03-28T15:00:00-07:00",
    },
    {
        "jira_key": "ZTAEX-2348",
        "jira_id": "6630005",
        "issue_type": "Bug",
        "summary": "Feature flag check fails for cloudsso customers with empty entitlements",
        "status": "Done",
        "priority": "Highest",
        "assignee_name": "Luis Chang",
        "assignee_account_id": "712020:532953f3-75ad-4375-b04a-6666aecb6da3",
        "created_at": "2026-03-19T07:00:00-07:00",
        "updated_at": "2026-03-22T10:00:00-07:00",
        "resolved_at": "2026-03-22T10:00:00-07:00",
    },
]

# ── Real GitHub PRs from ZT-trustedpath ──────────────────────────────

GITHUB_PRS = [
    {
        "github_pr_id": 3471738068,
        "number": 48465,
        "title": "[ZTMAP-3510] - Add preview mode component",
        "author": "ylyychak",
        "state": "open",
        "head_branch": "ylychak/ZTMAP-3510_directory_configuration_preview",
        "base_branch": "master",
        "additions": 342,
        "deletions": 18,
        "opened_at": "2026-03-31T12:09:25+00:00",
        "merged_at": None,
    },
    # Simulated PRs linked to our Jira issues for richer demo data
    {
        "github_pr_id": 3470000001,
        "number": 48450,
        "title": "[ZTAEX-2358] Update test CODEOWNERS for adminserv",
        "author": "largotte-cisco",
        "state": "merged",
        "head_branch": "largotte/ZTAEX-2358-update-codeowners",
        "base_branch": "master",
        "additions": 87,
        "deletions": 23,
        "ai_lines_added": 45,
        "ai_percentage": 41.3,
        "opened_at": "2026-03-28T14:00:00+00:00",
        "first_review_requested_at": "2026-03-28T14:30:00+00:00",
        "first_review_at": "2026-03-29T09:15:00+00:00",
        "approved_at": "2026-03-31T10:00:00+00:00",
        "merged_at": "2026-03-31T11:00:00+00:00",
    },
    {
        "github_pr_id": 3470000002,
        "number": 48430,
        "title": "[ZTAEX-2340] Migrate adminserv webpack to rspack",
        "author": "largotte-cisco",
        "state": "merged",
        "head_branch": "largotte/ZTAEX-2340-rspack-migration",
        "base_branch": "master",
        "additions": 523,
        "deletions": 412,
        "ai_lines_added": 280,
        "ai_percentage": 53.5,
        "opened_at": "2026-03-14T10:00:00+00:00",
        "first_review_requested_at": "2026-03-14T10:30:00+00:00",
        "first_review_at": "2026-03-15T08:00:00+00:00",
        "approved_at": "2026-03-18T14:00:00+00:00",
        "merged_at": "2026-03-19T09:00:00+00:00",
    },
    {
        "github_pr_id": 3470000003,
        "number": 48420,
        "title": "[ZTAEX-2335] Fix Safari login redirect loop",
        "author": "bryduo",
        "state": "merged",
        "head_branch": "bryduo/ZTAEX-2335-safari-redirect-fix",
        "base_branch": "master",
        "additions": 34,
        "deletions": 12,
        "ai_lines_added": 8,
        "ai_percentage": 17.4,
        "opened_at": "2026-03-08T16:00:00+00:00",
        "first_review_requested_at": "2026-03-08T16:10:00+00:00",
        "first_review_at": "2026-03-09T10:00:00+00:00",
        "approved_at": "2026-03-10T09:00:00+00:00",
        "merged_at": "2026-03-10T10:00:00+00:00",
    },
    {
        "github_pr_id": 3470000004,
        "number": 48410,
        "title": "[ZTAEX-2330] Add Duo Desktop health check endpoint",
        "author": "bsharko-cisco",
        "state": "merged",
        "head_branch": "bsharko/ZTAEX-2330-health-check-endpoint",
        "base_branch": "master",
        "additions": 456,
        "deletions": 32,
        "ai_lines_added": 310,
        "ai_percentage": 63.7,
        "opened_at": "2026-03-10T09:00:00+00:00",
        "first_review_requested_at": "2026-03-10T09:30:00+00:00",
        "first_review_at": "2026-03-11T14:00:00+00:00",
        "approved_at": "2026-03-15T11:00:00+00:00",
        "merged_at": "2026-03-16T09:00:00+00:00",
    },
    {
        "github_pr_id": 3470000005,
        "number": 48440,
        "title": "[ZTAEX-2345] Implement session trust quarantine API v2",
        "author": "bryduo",
        "state": "merged",
        "head_branch": "bryduo/ZTAEX-2345-session-trust-v2",
        "base_branch": "master",
        "additions": 678,
        "deletions": 145,
        "ai_lines_added": 420,
        "ai_percentage": 55.0,
        "opened_at": "2026-03-20T08:00:00+00:00",
        "first_review_requested_at": "2026-03-20T08:15:00+00:00",
        "first_review_at": "2026-03-21T10:00:00+00:00",
        "approved_at": "2026-03-26T15:00:00+00:00",
        "merged_at": "2026-03-27T09:00:00+00:00",
    },
    {
        "github_pr_id": 3470000006,
        "number": 48445,
        "title": "[ZTAEX-2348] Fix feature flag check for cloudsso",
        "author": "largotte-cisco",
        "state": "merged",
        "head_branch": "largotte/ZTAEX-2348-fix-ff-cloudsso",
        "base_branch": "master",
        "additions": 28,
        "deletions": 5,
        "ai_lines_added": 3,
        "ai_percentage": 9.1,
        "opened_at": "2026-03-20T14:00:00+00:00",
        "first_review_requested_at": "2026-03-20T14:05:00+00:00",
        "first_review_at": "2026-03-20T16:00:00+00:00",
        "approved_at": "2026-03-21T08:00:00+00:00",
        "merged_at": "2026-03-21T09:00:00+00:00",
    },
    {
        "github_pr_id": 3470000007,
        "number": 48455,
        "title": "[ZTAEX-2353] AMR validation full match",
        "author": "bryduo",
        "state": "open",
        "head_branch": "bryduo/ZTAEX-2353-amr-validation",
        "base_branch": "master",
        "additions": 156,
        "deletions": 42,
        "ai_lines_added": 95,
        "ai_percentage": 48.2,
        "opened_at": "2026-03-30T10:00:00+00:00",
        "first_review_requested_at": "2026-03-30T10:15:00+00:00",
        "first_review_at": "2026-03-31T09:00:00+00:00",
        "merged_at": None,
    },
    {
        "github_pr_id": 3470000008,
        "number": 48460,
        "title": "[ZTAEX-2347] Fix pageSubtitle maxWidth",
        "author": "bsharko-cisco",
        "state": "open",
        "head_branch": "bsharko/ZTAEX-2347-page-subtitle-width",
        "base_branch": "master",
        "additions": 12,
        "deletions": 4,
        "ai_lines_added": 6,
        "ai_percentage": 37.5,
        "opened_at": "2026-04-01T08:00:00+00:00",
        "first_review_requested_at": "2026-04-01T08:10:00+00:00",
        "first_review_at": None,
        "merged_at": None,
    },
]

# ── Simulated transitions for resolved issues ────────────────────────

TRANSITIONS_MAP = {
    "ZTAEX-2358": [
        ("Backlog", "Selected for Development", "2026-03-27T09:00:00+00:00"),
        ("Selected for Development", "In Progress", "2026-03-28T08:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-28T14:00:00+00:00"),
        ("Code Review", "Done", "2026-04-03T09:16:20+00:00"),
    ],
    "ZTAEX-2340": [
        ("Backlog", "In Progress", "2026-03-11T09:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-14T10:00:00+00:00"),
        ("Code Review", "Done", "2026-03-20T14:30:00+00:00"),
    ],
    "ZTAEX-2335": [
        ("Backlog", "In Progress", "2026-03-06T08:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-08T16:00:00+00:00"),
        ("Code Review", "Done", "2026-03-12T16:00:00+00:00"),
    ],
    "ZTAEX-2330": [
        ("Backlog", "In Progress", "2026-03-03T09:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-10T09:00:00+00:00"),
        ("Code Review", "Changes Requested", "2026-03-12T14:00:00+00:00"),
        ("Changes Requested", "In Progress", "2026-03-13T08:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-14T10:00:00+00:00"),
        ("Code Review", "Done", "2026-03-18T11:00:00+00:00"),
    ],
    "ZTAEX-2345": [
        ("Backlog", "In Progress", "2026-03-16T08:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-20T08:00:00+00:00"),
        ("Code Review", "Done", "2026-03-28T15:00:00+00:00"),
    ],
    "ZTAEX-2348": [
        ("Backlog", "In Progress", "2026-03-19T10:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-20T14:00:00+00:00"),
        ("Code Review", "Done", "2026-03-22T10:00:00+00:00"),
    ],
    "ZTAEX-2353": [
        ("Backlog", "In Progress", "2026-03-27T09:00:00+00:00"),
        ("In Progress", "Code Review", "2026-03-30T10:00:00+00:00"),
    ],
    "ZTAEX-2347": [
        ("Backlog", "In Progress", "2026-03-25T08:00:00+00:00"),
        ("In Progress", "Code Review", "2026-04-01T08:00:00+00:00"),
    ],
}


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    if len(s) > 5 and s[-5] in "+-" and ":" not in s[-5:]:
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # 1. Create repository
        repo = Repository(github_repo="cisco-sbg/ZT-trustedpath", jira_project_key="ZTAEX")
        db.add(repo)
        await db.flush()

        # 2. Insert Jira issues
        issue_map: dict[str, Issue] = {}
        for data in JIRA_ISSUES:
            issue = Issue(
                jira_key=data["jira_key"],
                jira_id=data["jira_id"],
                issue_type=data["issue_type"],
                summary=data["summary"],
                status=data["status"],
                priority=data["priority"],
                assignee_name=data["assignee_name"],
                assignee_account_id=data["assignee_account_id"],
                created_at=_parse_dt(data["created_at"]),
                updated_at=_parse_dt(data["updated_at"]),
                resolved_at=_parse_dt(data["resolved_at"]),
                repository_id=repo.id,
            )
            db.add(issue)
            await db.flush()
            issue_map[data["jira_key"]] = issue

        print(f"Inserted {len(issue_map)} Jira issues")

        # 3. Insert transitions
        transition_count = 0
        for jira_key, transitions in TRANSITIONS_MAP.items():
            issue = issue_map.get(jira_key)
            if not issue:
                continue
            for from_status, to_status, ts in transitions:
                t = IssueTransition(
                    issue_id=issue.id,
                    from_status=from_status,
                    to_status=to_status,
                    transitioned_at=_parse_dt(ts),
                )
                db.add(t)
                transition_count += 1
        await db.flush()
        print(f"Inserted {transition_count} transitions")

        # 4. Insert GitHub PRs and link to issues
        pr_map: dict[int, PullRequest] = {}
        for data in GITHUB_PRS:
            pr = PullRequest(
                github_pr_id=data["github_pr_id"],
                number=data["number"],
                title=data["title"],
                author=data["author"],
                state=data["state"],
                head_branch=data["head_branch"],
                base_branch=data["base_branch"],
                additions=data.get("additions"),
                deletions=data.get("deletions"),
                ai_lines_added=data.get("ai_lines_added", 0),
                ai_percentage=data.get("ai_percentage", 0.0),
                opened_at=_parse_dt(data["opened_at"]),
                first_review_requested_at=_parse_dt(data.get("first_review_requested_at")),
                first_review_at=_parse_dt(data.get("first_review_at")),
                approved_at=_parse_dt(data.get("approved_at")),
                merged_at=_parse_dt(data.get("merged_at")),
                repository_id=repo.id,
            )
            db.add(pr)
            await db.flush()
            pr_map[data["number"]] = pr

        print(f"Inserted {len(pr_map)} PRs")

        # 5. Link PRs to issues via branch name matching
        import re
        linked = 0
        for pr in pr_map.values():
            matches = re.findall(r"[A-Z][A-Z0-9]+-\d+", pr.head_branch)
            if not matches:
                matches = re.findall(r"[A-Z][A-Z0-9]+-\d+", pr.title)
            if matches:
                issue = issue_map.get(matches[0])
                if issue:
                    pr.issue_id = issue.id
                    linked += 1

        await db.flush()
        print(f"Linked {linked} PRs to issues")

        # 6. Insert sample commits + AI attributions for merged PRs
        commit_count = 0
        attr_count = 0
        agents = ["copilot", "codex", "claude", "copilot", "copilot"]
        models = ["gpt-4", "gpt-4", "sonnet-3.5", "gpt-4o", "gpt-4"]

        for pr in pr_map.values():
            if not pr.merged_at:
                continue
            # Create 1-3 commits per merged PR
            num_commits = random.randint(1, 3)
            for i in range(num_commits):
                sha = f"{pr.number:05d}{i:02d}" + "a" * 33
                c = Commit(
                    sha=sha,
                    message=f"commit {i+1} for {pr.title}",
                    author=pr.author,
                    committed_at=pr.opened_at + timedelta(hours=random.randint(1, 48)),
                    additions=random.randint(10, 200),
                    deletions=random.randint(0, 50),
                    pull_request_id=pr.id,
                )
                db.add(c)
                await db.flush()
                commit_count += 1

                # Add AI attributions if PR has AI code
                if pr.ai_percentage and pr.ai_percentage > 10:
                    num_attrs = random.randint(1, 4)
                    for j in range(num_attrs):
                        start_line = random.randint(1, 100)
                        end_line = start_line + random.randint(5, 40)
                        agent_idx = random.randint(0, len(agents) - 1)
                        attr = AIAttribution(
                            commit_id=c.id,
                            file_path=random.choice([
                                "adminserv/handlers/auth.py",
                                "lib-python/duo/auth/session.py",
                                "endpointhealthserv/health_check.py",
                                "cloudsso/services/session_trust.py",
                                "adminserv/webpack.config.ts",
                                "test/js/admin/auth.test.ts",
                            ]),
                            ai_lines_start=start_line,
                            ai_lines_end=end_line,
                            agent=agents[agent_idx],
                            model=models[agent_idx],
                            confidence=round(random.uniform(0.7, 0.99), 2),
                        )
                        db.add(attr)
                        attr_count += 1

        await db.flush()
        print(f"Inserted {commit_count} commits, {attr_count} AI attributions")

        # 7. Insert sample review comments
        comment_count = 0
        for pr in pr_map.values():
            if not pr.first_review_at:
                continue
            num_comments = random.randint(1, 5)
            for i in range(num_comments):
                rc = ReviewComment(
                    github_comment_id=random.randint(100000, 999999),
                    pull_request_id=pr.id,
                    author=random.choice(["reviewer1", "reviewer2", "bryduo", "largotte-cisco"]),
                    body=random.choice([
                        "Looks good, minor nit on naming.",
                        "Can we add a test for this edge case?",
                        "This AI-generated block needs better error handling.",
                        "LGTM",
                        "Consider extracting this into a utility function.",
                        "The AI suggestion here is good but needs a bounds check.",
                    ]),
                    file_path=random.choice([
                        "adminserv/handlers/auth.py",
                        "lib-python/duo/auth/session.py",
                        "endpointhealthserv/health_check.py",
                    ]),
                    line_number=random.randint(1, 150),
                    is_on_ai_code=random.choice([True, False, True, None]),
                    is_bot=False,
                    state=random.choice(["commented", "approved", "changes_requested"]),
                    created_at=pr.first_review_at + timedelta(hours=random.randint(0, 24)),
                )
                db.add(rc)
                comment_count += 1

        await db.flush()
        print(f"Inserted {comment_count} review comments")

        await db.commit()
        print("\n✅ Seed complete!")

    # 8. Run enrichment: compute cycle metrics
    print("\nRunning enrichment...")
    async with async_session() as db:
        from app.enrichment.cycle_metrics import recompute_all as recompute_cycle
        from app.enrichment.quality_metrics import recompute_all as recompute_quality

        cycle_count = await recompute_cycle(db)
        await db.commit()
        print(f"  Computed cycle metrics for {cycle_count} issues")

        quality_count = await recompute_quality(db)
        await db.commit()
        print(f"  Computed quality metrics for {quality_count} PRs")

    print("\n🎉 Database seeded and enriched! API should now return real metrics.")


if __name__ == "__main__":
    asyncio.run(seed())

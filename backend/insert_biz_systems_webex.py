#!/usr/bin/env python3
"""Insert Webex messages from business-systems-reviews room."""
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, ".")

from sqlalchemy import select
from app.db.models import Base, WebexMessage
from app.db.session import async_session, engine

# Business Systems Reviews room
ROOM_ID = "4c9b73f0-98c9-11f0-b9d2-fb6425dea2e0"

MESSAGES = [
    # Deployment notifications
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZWU5ZDExNjAtMzM0Zi0xMWYxLTg0ZDktZGI1NDU3MzUzZWE0",
        "personId": "jamrusso-556237393@cisco.com",
        "text": "Running Install Trustedpath: billing-first with limit deployment_billing-first launched by poojdesh@duosecurity.com",
        "created": "2026-04-08T13:36:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYmYyNDExYjAtMzM0OC0xMWYxLWExNmYtZmQ0NTk3OWNiZjYw",
        "personId": "jamrusso-556237393@cisco.com",
        "text": "Install Trustedpath: billing-first succeeded https://awx-prod.k8s.mgmt.5c10.org/#/jobs/playbook/78209",
        "created": "2026-04-08T12:44:00.000Z",
        "parentId": None,
    },
    # PR review requests from diffatron
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZjFiYjg4ZTAtMzMyMi0xMWYxLTkxMjQtMGYxMjI3OTFhMGFk",
        "personId": "diffatron@webex.bot",
        "text": "feat: turning on flip n crypt for standard api deployments https://github.com/cisco-sbg/ZT-trustedpath/pull/45050 by Nick Aspinall is ready for review.",
        "created": "2026-04-08T08:14:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYzRhOTg5ZDAtMzJlOS0xMWYxLWE3NmQtYjkxZjBlMjUwOWFl",
        "personId": "diffatron@webex.bot",
        "text": "Creditserv log statement changes in send_notification to catch deleted cids https://github.com/cisco-sbg/ZT-trustedpath/pull/49046 by Dinesh Kumar K B is ready for review.",
        "created": "2026-04-08T01:25:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvNDRlNjc3NDAtMzI2Yi0xMWYxLWFkM2EtMWRmNmQwOWM0NGM5",
        "personId": "diffatron@webex.bot",
        "text": "Add internet-facing ALB to billing-first for Mulesoft integration https://github.com/cisco-sbg/ZT-ops/pull/46078 by Shivam Kalra is ready for review.",
        "created": "2026-04-07T10:19:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMjU0YWViNTAtMzI1Mi0xMWYxLWEzNjEtZTc1MDkxODQ0MWM3",
        "personId": "diffatron@webex.bot",
        "text": "Fixed the DB validation method to use fetchone instead of rowcount https://github.com/cisco-sbg/ZT-trustedpath/pull/49046 by Dinesh Kumar K B is ready for review.",
        "created": "2026-04-07T07:19:00.000Z",
        "parentId": None,
    },
    # Human review requests
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMzAwNTdlNjAtMzFhNC0xMWYxLTgzMzUtZDk3ZDlkMzQwMzg2",
        "personId": "shikalra@cisco.com",
        "text": "Hi Team, need Duo India Biz Systems owner review on the PR to add internet-facing ALB to billing-first for Mulesoft integration. https://github.com/cisco-sbg/ZT-ops/pull/46078",
        "created": "2026-04-06T10:34:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvOWVhZDVlNjAtMzE3Ni0xMWYxLWJjZDMtYmJhMWEyNDgzMTQ3",
        "personId": "kriskum5@cisco.com",
        "text": "Hi team, Looking for review https://github.com/cisco-sbg/ZT-trustedpath/pull/49023",
        "created": "2026-04-06T05:08:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZjgwNGEzMzAtMmY2Mi0xMWYxLWJmMzYtMWZkYTU0Nzg4MDM1",
        "personId": "joscheng@cisco.com",
        "text": "Looking for a review on this PR to remove an unnecessary dependency: https://github.com/cisco-sbg/ZT-trustedpath/pull/48664",
        "created": "2026-04-03T13:42:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYTI4ZGNjOTAtMmRmNy0xMWYxLTk3MjQtZGQ2MWZmN2JlZTkx",
        "personId": "joscheng@cisco.com",
        "text": "Small PR to remove unnecessary dependency: https://github.com/cisco-sbg/ZT-trustedpath/pull/48664",
        "created": "2026-04-01T18:21:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZjM0Mzk2ODAtMmNlMi0xMWYxLTkxZmMtYmYwMmY0OWI0MDQ4",
        "personId": "shikalra@cisco.com",
        "text": "Hi Team, please review - billing usage data api POC https://github.com/cisco-sbg/ZT-trustedpath/pull/47839",
        "created": "2026-03-31T09:21:00.000Z",
        "parentId": None,
    },
    # More bot PRs
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvNjNkZGZiODAtMmVkNS0xMWYxLTk5YzQtNWYxYTIwYjIxNjlm",
        "personId": "diffatron@webex.bot",
        "text": "Merge duo_aws into lib-python-core https://github.com/cisco-sbg/ZT-trustedpath/pull/48795 by Marcus Stojcevich is ready for review.",
        "created": "2026-04-02T20:49:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvODBiZGRkZjAtMmVhZS0xMWYxLWI1YWEtMjljZDQyYjE4YWY1",
        "personId": "diffatron@webex.bot",
        "text": "feat(ci): Add CI failure remediation and flaky test analysis workflows https://github.com/cisco-sbg/ZT-trustedpath/pull/46390 by Hanyu Xiao is ready for review.",
        "created": "2026-04-02T16:10:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYjkzMWYzZTAtMmVhYi0xMWYxLThkZjEtZDE4MzE0MTZkYTRi",
        "personId": "diffatron@webex.bot",
        "text": "chore(ci): Deprecating Gitlab SME Group from Codeowners https://github.com/cisco-sbg/ZT-trustedpath/pull/48543 by AJ Rasmussen is ready for review.",
        "created": "2026-04-02T15:50:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYjlmNzE4NTAtMmQ5ZC0xMWYxLThiNzctNTlhNTAwZDBmYTU3",
        "personId": "diffatron@webex.bot",
        "text": "Created new serv and api for billing usage data api [POC] https://github.com/cisco-sbg/ZT-trustedpath/pull/47839 by Shivam Kalra is ready for review.",
        "created": "2026-04-01T07:38:00.000Z",
        "parentId": None,
    },
]


def parse_datetime(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    inserted = 0
    skipped = 0

    async with async_session() as db:
        for msg in MESSAGES:
            existing = await db.execute(
                select(WebexMessage).where(WebexMessage.webex_message_id == msg["id"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            webex_msg = WebexMessage(
                webex_message_id=msg["id"],
                room_id=ROOM_ID,
                person_id=msg["personId"],
                text=msg["text"],
                parent_message_id=msg["parentId"],
                created_at=parse_datetime(msg["created"]),
            )
            db.add(webex_msg)
            inserted += 1

        await db.commit()

    print(f"Inserted: {inserted}, Skipped: {skipped}")
    print("Business Systems Webex messages loaded!")


if __name__ == "__main__":
    asyncio.run(main())

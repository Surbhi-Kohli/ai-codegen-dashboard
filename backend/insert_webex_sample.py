#!/usr/bin/env python3
"""Insert sample Webex messages from the omni-platform-reviews room."""
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy import select
from app.db.models import Base, WebexMessage
from app.db.session import async_session, engine

# Sample messages from omni-platform-reviews room (real data from MCP)
ROOM_ID = "ee97c270-a9a0-11f0-aabe-555961c5d051"

MESSAGES = [
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvNzVkOThkOTAtMzM1My0xMWYxLWFmM2UtMTM5MTliMjM3ZWMw",
        "personId": "diffatron@webex.bot",
        "text": "chore(omniserv): Update trivial imports from lib-python to lib-python-core https://github.com/cisco-sbg/ZT-trustedpath/pull/48574 by Josh Cheng is ready for review.",
        "created": "2026-04-08T14:01:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMzAzM2ZkZjAtMzM1MC0xMWYxLWI1ZTktNmI2YTUzOTY4MmRl",
        "personId": "diffatron@webex.bot",
        "text": "feat(awx): Add release track groups for proxy first, dev, fed-dev (ZTBAR-1257) https://github.com/cisco-sbg/ZT-ops/pull/46383 by David Caballero is ready for review.",
        "created": "2026-04-08T13:38:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvODI2ZGQzNTAtMzM0ZC0xMWYxLTlkMGYtODk3NzE0NjFhMzI5",
        "personId": "diffatron@webex.bot",
        "text": "Add telephony refill date (billing_tracker) alignment when billing_start changes in Omniserv https://github.com/cisco-sbg/ZT-trustedpath/pull/49123 by SurbhiKohli is ready for review.",
        "created": "2026-04-08T13:19:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMzIyNjUzYjAtMzMzMi0xMWYxLWExZTQtYjkwODQ1OGU0ZDIz",
        "personId": "diffatron@webex.bot",
        "text": "ZTOP-2736-Fix styles after magnetic upgrade https://github.com/cisco-sbg/ZT-trustedpath/pull/49299 by Mariia Lysenko is ready for review.",
        "created": "2026-04-08T10:03:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZjFkNGI2MzAtMzMyMi0xMWYxLWE0YzMtZDc2ZTE4MDdiMDcx",
        "personId": "diffatron@webex.bot",
        "text": "feat: turning on flip n crypt for standard api deployments https://github.com/cisco-sbg/ZT-trustedpath/pull/45050 by Nick Aspinall is ready for review.",
        "created": "2026-04-08T08:14:00.000Z",
        "parentId": None,
    },
    # Human replies in threads
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYjEzMzYzZDAtMzFkYi0xMWYxLTlkNmMtNDNkZThhMjdmZDYy",
        "personId": "dczmer@cisco.com",
        "text": "Sorry you may notice that messages from bots fill this room up so fast that we frequently don't even see your messages or threads here because they go...",
        "created": "2026-04-06T17:11:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMTExN2VhODAtMmM0ZC0xMWYxLTk2MDgtMmRkNjU4MWQwZmIy",
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvNzYxOTVmNjAtMzFkNy0xMWYxLThiNzItOWY3ZDY3ODdjYWJl",
        "personId": "surkohli@cisco.com",
        "text": "hi Siddharth Shah, Dave Czmer Would you please help here for the review. Thanks",
        "created": "2026-04-06T16:41:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMTExN2VhODAtMmM0ZC0xMWYxLTk2MDgtMmRkNjU4MWQwZmIy",
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMzI2NzYyNjAtMzFkNC0xMWYxLTg5OTMtYzc1OGZmOGJmZTFh",
        "personId": "sidshah2@cisco.com",
        "text": "will yall deploy 337 on first to test? not sure if its ok to merge\nyep, we can do this!",
        "created": "2026-04-06T16:18:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZDFjNWJkOTAtMmY1Yy0xMWYxLTg4N2MtZGJlYmJlZjA2Zjk3",
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMDkzMGUyNDAtMzFiYi0xMWYxLTkxMjQtMGYxMjI3OTFhMGFk",
        "personId": "dczmer@cisco.com",
        "text": "We can approve this but the business systems team are the codeowners and we are not blocking reviewers. I can approve it if the India team is not avai...",
        "created": "2026-04-06T13:18:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvM2IwNzY5YjAtMzFiMS0xMWYxLWE4NTYtZTU3MDY1YTg1MjVl",
    },
    # Original PR request that got a reply
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvM2IwNzY5YjAtMzFiMS0xMWYxLWE4NTYtZTU3MDY1YTg1MjVl",
        "personId": "shikalra@cisco.com",
        "text": "Hi Team, please review the PR to add internet-facing ALB to billing-first for Mulesoft integration. https://github.com/cisco-sbg/ZT-ops/pull/46078",
        "created": "2026-04-06T12:07:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZTg4MDkxMjAtMzE4NC0xMWYxLWJhZjctN2JjMGZmODA2MjVi",
        "personId": "vipurohi@cisco.com",
        "text": "Prudhivi / Ben (not tagging, as it's after hours for you) Can you please check and do the needful, thank you CC: Surbhi Kaushik Owary",
        "created": "2026-04-06T06:50:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMTExN2VhODAtMmM0ZC0xMWYxLTk2MDgtMmRkNjU4MWQwZmIy",
    },
    # The parent message that got multiple replies
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvMTExN2VhODAtMmM0ZC0xMWYxLTk2MDgtMmRkNjU4MWQwZmIy",
        "personId": "surkohli@cisco.com",
        "text": "Hi team, requesting review for PR https://github.com/cisco-sbg/ZT-trustedpath/pull/49000 - telephony billing alignment feature",
        "created": "2026-04-03T10:00:00.000Z",
        "parentId": None,
    },
    # Another thread with response
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZDFjNWJkOTAtMmY1Yy0xMWYxLTg4N2MtZGJlYmJlZjA2Zjk3",
        "personId": "hharajly@cisco.com",
        "text": "Need review for https://github.com/cisco-sbg/ZT-trustedpath/pull/48900 - deployment config changes",
        "created": "2026-04-04T14:00:00.000Z",
        "parentId": None,
    },
    {
        "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvYmRiNTY3YTAtMzFiNS0xMWYxLWI4ZjUtMTkyZmZkMjhjMmUx",
        "personId": "hharajly@cisco.com",
        "text": "Siddharth Shah i asked engineering if the freeze is done with so we can test on first, but how should we handle the AT that dave mentioned? will yall ...",
        "created": "2026-04-06T12:40:00.000Z",
        "parentId": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvZDFjNWJkOTAtMmY1Yy0xMWYxLTg4N2MtZGJlYmJlZjA2Zjk3",
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
            # Check if exists
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
    print("Webex messages loaded successfully!")


if __name__ == "__main__":
    asyncio.run(main())

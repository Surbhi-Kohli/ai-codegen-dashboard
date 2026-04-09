#!/usr/bin/env python3
"""
Backfill Webex messages from MCP tool output.

Usage:
1. Use MCP to fetch messages from a review room
2. Save the JSON output to a file
3. Run: python backfill_webex.py <messages.json> <room_id>

The script will:
- Parse PR URLs from messages to link them to PRs
- Store messages with thread relationships
- Calculate response times for PR review requests
"""
import asyncio
import json
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import select

# Add app to path
sys.path.insert(0, ".")

from app.db.models import PullRequest, Repository, WebexMessage
from app.db.session import async_session, engine
from app.db.models import Base


# GitHub PR URL pattern
PR_URL_PATTERN = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")


def parse_github_pr_url(text: str) -> tuple[str, int] | None:
    """Extract repo and PR number from GitHub PR URL in message text."""
    if not text:
        return None
    match = PR_URL_PATTERN.search(text)
    if match:
        return match.group(1), int(match.group(2))
    return None


def parse_webex_datetime(dt_str: str) -> datetime:
    """Parse Webex datetime (ISO 8601)."""
    dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)


async def backfill_messages(messages: list[dict], room_id: str) -> dict:
    """Store Webex messages and link to PRs."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stats = {
        "total": len(messages),
        "inserted": 0,
        "skipped": 0,
        "linked_to_prs": 0,
    }

    async with async_session() as db:
        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            # Check if already exists
            existing = await db.execute(
                select(WebexMessage).where(WebexMessage.webex_message_id == msg_id)
            )
            if existing.scalar_one_or_none():
                stats["skipped"] += 1
                continue

            # Extract text from message
            text = msg.get("text") or msg.get("markdown") or ""

            # Try to link to PR
            pr_id = None
            pr_info = parse_github_pr_url(text)
            if pr_info:
                repo_name, pr_number = pr_info
                # Find the PR in our database
                result = await db.execute(
                    select(PullRequest)
                    .join(Repository)
                    .where(
                        Repository.github_repo == repo_name,
                        PullRequest.number == pr_number,
                    )
                )
                pr = result.scalar_one_or_none()
                if pr:
                    pr_id = pr.id
                    stats["linked_to_prs"] += 1

            # Parse created timestamp
            created_str = msg.get("created")
            if not created_str:
                continue
            created_at = parse_webex_datetime(created_str)

            # Create message record
            webex_msg = WebexMessage(
                webex_message_id=msg_id,
                room_id=room_id,
                person_id=msg.get("personId", ""),
                text=text[:5000] if text else None,  # Truncate long messages
                parent_message_id=msg.get("parentId"),
                created_at=created_at,
                pull_request_id=pr_id,
            )
            db.add(webex_msg)
            stats["inserted"] += 1

        await db.commit()

    return stats


async def main():
    if len(sys.argv) < 3:
        print("Usage: python backfill_webex.py <messages.json> <room_id>")
        print("\nAlternatively, paste JSON directly:")
        print("  echo '<json>' | python backfill_webex.py - <room_id>")
        sys.exit(1)

    messages_file = sys.argv[1]
    room_id = sys.argv[2]

    # Read messages from file or stdin
    if messages_file == "-":
        data = sys.stdin.read()
    else:
        with open(messages_file) as f:
            data = f.read()

    # Parse JSON - handle both array and object with messages key
    parsed = json.loads(data)
    if isinstance(parsed, list):
        messages = parsed
    elif isinstance(parsed, dict) and "messages" in parsed:
        messages = parsed["messages"]
    else:
        print("Error: Expected JSON array or object with 'messages' key")
        sys.exit(1)

    print(f"Processing {len(messages)} messages from room {room_id}...")
    stats = await backfill_messages(messages, room_id)

    print(f"\nResults:")
    print(f"  Total messages: {stats['total']}")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Skipped (already exist): {stats['skipped']}")
    print(f"  Linked to PRs: {stats['linked_to_prs']}")


if __name__ == "__main__":
    asyncio.run(main())

"""
B4: git-ai Batch Extractor

Primary hackathon ingestion path for AI attribution data.
Runs git-ai CLI commands against a local repo clone to extract
per-commit stats and line-level attribution from git notes.

Usage:
    python -m app.ingestion.gitai_extractor /path/to/repo [--since=2026-03-01]
"""
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIAttribution, Commit
from app.db.session import async_session, engine
from app.db.models import Base

logger = logging.getLogger(__name__)


def run_git(args: list[str], cwd: str) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("git %s failed: %s", " ".join(args), result.stderr.strip())
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("git command error: %s", e)
        return None


def get_commit_shas(repo_path: str, since: str | None = None) -> list[str]:
    """Get commit SHAs from the repo, optionally filtered by date."""
    args = ["log", "--all", "--format=%H", "--no-merges", "--invert-grep", "--grep=Notes added by", "--grep=Notes removed by"]
    if since:
        args.append(f"--since={since}")
    output = run_git(args, repo_path)
    if not output:
        return []
    return output.splitlines()


def get_ai_stats(repo_path: str, sha: str) -> dict | None:
    """
    Run `git ai stats <sha> --json` and parse the output.

    Expected JSON structure:
    {
      "commit": "<sha>",
      "human_additions": 45,
      "ai_additions": 120,
      "mixed_additions": 15,
      "ai_accepted": 105,
      "total_ai_additions": 135,
      "total_ai_deletions": 8,
      "time_waiting_for_ai": 42,
      "tool_model_breakdown": [
        {"tool": "cursor", "model": "claude-sonnet-4-20250514", "additions": 80, "accepted": 70},
        {"tool": "copilot", "model": "gpt-4", "additions": 40, "accepted": 35}
      ]
    }
    """
    output = run_git(["ai", "stats", sha, "--json"], repo_path)
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        logger.warning("Failed to parse git ai stats JSON for %s", sha)
        return None


def get_ai_notes(repo_path: str, sha: str) -> dict | None:
    """
    Read git notes from refs/notes/ai for a specific commit.

    Expected structure (one note per commit, JSON):
    {
      "<prompt_id>": {
        "agent_id": {"tool": "cursor", "model": "claude-sonnet-4-20250514"},
        "human_author": "aparey",
        "messages_url": "https://...",
        "ranges": {
          "src/handler.py": [[10, 45], [80, 95]],
          "src/utils.py": [[1, 30]]
        }
      }
    }
    """
    output = run_git(["notes", "--ref=ai", "show", sha], repo_path)
    if not output:
        return None

    # git-ai v3.0.0 format: preamble lines + "---" separator + JSON body
    json_str = output
    if "---" in output:
        parts = output.split("---", 1)
        json_str = parts[1].strip()
        preamble = parts[0].strip()

    try:
        parsed = json.loads(json_str)
        # v3.0.0 wraps prompts under a "prompts" key; flatten for our extractor
        if "prompts" in parsed:
            return {"_preamble": preamble if "---" in output else None, **parsed}
        return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse git notes JSON for %s", sha)
        return None


def get_ai_blame(repo_path: str, file_path: str) -> list[dict] | None:
    """
    Run `git ai blame <file> --json` for line-level attribution.
    Returns list of line attribution entries.
    """
    output = run_git(["ai", "blame", file_path, "--json"], repo_path)
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        logger.warning("Failed to parse git ai blame JSON for %s", file_path)
        return None


def _parse_preamble_ranges(preamble: str) -> dict[str, dict[str, list[list[int]]]]:
    """Parse v3.0.0 preamble lines like 'file.py\\n  prompt_id 1-10,20-30' into ranges."""
    result: dict[str, dict[str, list[list[int]]]] = {}
    current_file = None
    for line in preamble.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not line.startswith(" ") and not line.startswith("\t"):
            current_file = stripped
        elif current_file:
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                prompt_id, range_str = parts
                ranges: list[list[int]] = []
                for segment in range_str.split(","):
                    segment = segment.strip()
                    if "-" in segment:
                        try:
                            s, e = segment.split("-", 1)
                            ranges.append([int(s), int(e)])
                        except ValueError:
                            pass
                    else:
                        try:
                            n = int(segment)
                            ranges.append([n, n])
                        except ValueError:
                            pass
                if ranges:
                    result.setdefault(prompt_id, {}).setdefault(current_file, []).extend(ranges)
    return result


async def extract_commit(db: AsyncSession, repo_path: str, sha: str) -> bool:
    """Extract git-ai data for a single commit and upsert into DB."""
    result = await db.execute(select(Commit).where(Commit.sha == sha))
    commit = result.scalar_one_or_none()

    stats = get_ai_stats(repo_path, sha)

    if not commit:
        git_log = run_git(["log", "-1", "--format=%ae|%s|%aI", sha], repo_path)
        if not git_log:
            return False
        parts = git_log.split("|", 2)
        author = parts[0] if len(parts) > 0 else "unknown"
        message = parts[1] if len(parts) > 1 else ""
        committed_at_str = parts[2] if len(parts) > 2 else None

        committed_at = datetime.now(timezone.utc)
        if committed_at_str:
            try:
                committed_at = datetime.fromisoformat(committed_at_str)
            except ValueError:
                pass

        commit = Commit(
            sha=sha,
            message=message,
            author=author,
            committed_at=committed_at,
        )
        db.add(commit)
        await db.flush()

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

    notes = get_ai_notes(repo_path, sha)
    if notes:
        existing_attrs = await db.execute(
            select(AIAttribution.id).where(AIAttribution.commit_id == commit.id)
        )
        if not existing_attrs.scalars().first():
            # v3.0.0: prompts are under a "prompts" key; also handle preamble ranges
            prompts = notes.get("prompts", {})
            preamble = notes.get("_preamble", "")
            preamble_ranges = _parse_preamble_ranges(preamble) if preamble else {}

            if not prompts:
                prompts = {k: v for k, v in notes.items() if k not in ("_preamble", "schema_version", "git_ai_version", "base_commit_sha", "prompts")}

            for prompt_id, prompt_data in prompts.items():
                agent_id = prompt_data.get("agent_id", {})
                agent = agent_id.get("tool", "unknown")
                model = agent_id.get("model")
                human_author = prompt_data.get("human_author")
                messages_url = prompt_data.get("messages_url")
                ranges = prompt_data.get("ranges", preamble_ranges.get(prompt_id, {}))

                for file_path, line_ranges in ranges.items():
                    for line_range in line_ranges:
                        if len(line_range) >= 2:
                            attr = AIAttribution(
                                commit_id=commit.id,
                                file_path=file_path,
                                ai_lines_start=line_range[0],
                                ai_lines_end=line_range[1],
                                agent=agent,
                                model=model,
                                prompt_id=prompt_id,
                                human_author=human_author,
                                messages_url=messages_url,
                                raw_note=json.dumps(prompt_data),
                            )
                            db.add(attr)

    await db.flush()
    has_ai = stats is not None or notes is not None
    if has_ai:
        logger.info("Extracted AI data for %s", sha[:12])
    return has_ai


async def extract_repo(repo_path: str, since: str | None = None) -> dict:
    """
    Extract git-ai data for all commits in a repo.
    Returns summary stats.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    shas = get_commit_shas(repo_path, since)
    logger.info("Found %d commits to process%s", len(shas), f" (since {since})" if since else "")

    total = 0
    ai_commits = 0

    async with async_session() as db:
        for sha in shas:
            had_ai = await extract_commit(db, repo_path, sha)
            total += 1
            if had_ai:
                ai_commits += 1

            if total % 50 == 0:
                await db.commit()
                logger.info("Progress: %d/%d commits processed (%d with AI data)", total, len(shas), ai_commits)

        await db.commit()

    summary = {
        "total_commits_processed": total,
        "commits_with_ai_data": ai_commits,
        "repo_path": repo_path,
        "since": since,
    }
    logger.info("Extraction complete: %s", summary)
    return summary


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m app.ingestion.gitai_extractor /path/to/repo [--since=YYYY-MM-DD]")
        sys.exit(1)

    repo_path = sys.argv[1]
    if not Path(repo_path).is_dir():
        print(f"Error: {repo_path} is not a directory")
        sys.exit(1)

    since = None
    for arg in sys.argv[2:]:
        if arg.startswith("--since="):
            since = arg.split("=", 1)[1]

    summary = await extract_repo(repo_path, since)
    print(f"\nDone! {summary['commits_with_ai_data']}/{summary['total_commits_processed']} commits had AI data.")


if __name__ == "__main__":
    asyncio.run(main())

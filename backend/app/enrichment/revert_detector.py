"""
Line-level revert detection for AI-attributed code.

Instead of relying solely on commit messages containing "revert",
this module checks whether AI-attributed line ranges were actually
removed in subsequent commits by parsing unified diffs.
"""
import re
from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIAttribution, Commit, CommitFile, PullRequest


# Matches unified diff hunk headers: @@ -old_start,old_count +new_start,new_count @@
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")

# Threshold: if >= 50% of AI lines are deleted, flag as reverted
REVERT_THRESHOLD = 0.5


def parse_deleted_ranges(patch: str) -> list[tuple[int, int]]:
    """Parse a unified diff patch to extract line ranges deleted from the original file.

    Returns a list of (start, end) tuples representing inclusive line ranges
    in the *original* file that were deleted.
    """
    deleted_ranges: list[tuple[int, int]] = []
    current_old_line = 0
    run_start: int | None = None

    for line in patch.splitlines():
        hunk_match = _HUNK_RE.match(line)
        if hunk_match:
            # Flush any open run from previous hunk
            if run_start is not None:
                deleted_ranges.append((run_start, current_old_line - 1))
                run_start = None
            current_old_line = int(hunk_match.group(1))
            continue

        if current_old_line == 0:
            continue  # haven't seen a hunk header yet

        if line.startswith("-"):
            # This line was deleted from the original file
            if run_start is None:
                run_start = current_old_line
            current_old_line += 1
        elif line.startswith("+"):
            # Added line — doesn't advance old line counter
            if run_start is not None:
                deleted_ranges.append((run_start, current_old_line - 1))
                run_start = None
        else:
            # Context line — advances old line counter
            if run_start is not None:
                deleted_ranges.append((run_start, current_old_line - 1))
                run_start = None
            current_old_line += 1

    # Flush trailing run
    if run_start is not None:
        deleted_ranges.append((run_start, current_old_line - 1))

    return deleted_ranges


def compute_overlap(
    ai_ranges: list[tuple[int, int]],
    deleted_ranges: list[tuple[int, int]],
) -> int:
    """Count how many AI-attributed lines fall within deleted ranges.

    Both ai_ranges and deleted_ranges are lists of (start, end) inclusive tuples.
    """
    removed = 0
    for ai_start, ai_end in ai_ranges:
        for del_start, del_end in deleted_ranges:
            overlap_start = max(ai_start, del_start)
            overlap_end = min(ai_end, del_end)
            if overlap_start <= overlap_end:
                removed += overlap_end - overlap_start + 1
    return removed


async def detect_ai_line_removal(
    db: AsyncSession,
    pr: PullRequest,
    attributions: list[AIAttribution],
    window_days: int = 7,
) -> tuple[bool, float]:
    """Check if AI-attributed lines were removed in commits after this PR merged.

    Returns (reverted: bool, removal_ratio: float).
    """
    if not pr.merged_at or not attributions:
        return False, 0.0

    # Build {file_path: [(start, end), ...]} from attributions
    ai_file_ranges: dict[str, list[tuple[int, int]]] = {}
    total_ai_lines = 0
    for attr in attributions:
        ai_file_ranges.setdefault(attr.file_path, []).append(
            (attr.ai_lines_start, attr.ai_lines_end)
        )
        total_ai_lines += attr.ai_lines_end - attr.ai_lines_start + 1

    if total_ai_lines == 0:
        return False, 0.0

    revert_cutoff = pr.merged_at + timedelta(days=window_days)
    ai_file_paths = list(ai_file_ranges.keys())

    # Find CommitFiles from later commits in the same repo that touch AI-attributed files
    query = (
        select(CommitFile)
        .join(Commit, Commit.id == CommitFile.commit_id)
        .where(
            Commit.committed_at > pr.merged_at,
            Commit.committed_at <= revert_cutoff,
            Commit.repository_id == pr.repository_id,
            # Exclude the PR's own commits
            Commit.pull_request_id != pr.id,
            CommitFile.file_path.in_(ai_file_paths),
            CommitFile.status.in_(["modified", "removed"]),
        )
    )
    result = await db.execute(query)
    commit_files = result.scalars().all()

    if not commit_files:
        return False, 0.0

    total_removed = 0
    for cf in commit_files:
        ranges = ai_file_ranges.get(cf.file_path, [])
        if not ranges:
            continue

        if cf.status == "removed":
            # Entire file deleted — all AI lines in this file are reverted
            for start, end in ranges:
                total_removed += end - start + 1
        elif cf.patch:
            # Parse the diff to find which original lines were deleted
            deleted_ranges = parse_deleted_ranges(cf.patch)
            if deleted_ranges:
                total_removed += compute_overlap(ranges, deleted_ranges)

    removal_ratio = round(total_removed / total_ai_lines, 3) if total_ai_lines > 0 else 0.0
    reverted = removal_ratio >= REVERT_THRESHOLD

    return reverted, removal_ratio

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Jira-sourced entities ──────────────────────────────────────────────


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_repo: Mapped[str] = mapped_column(String(255), unique=True)  # owner/name
    jira_project_key: Mapped[str | None] = mapped_column(String(50))
    webex_review_room_id: Mapped[str | None] = mapped_column(String(255))
    webex_discussion_room_id: Mapped[str | None] = mapped_column(String(255))

    issues: Mapped[list["Issue"]] = relationship(back_populates="repository")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="repository")


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    github_username: Mapped[str | None] = mapped_column(String(255), unique=True)
    jira_account_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    webex_person_id: Mapped[str | None] = mapped_column(String(255), unique=True)


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jira_sprint_id: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(50))  # active, closed, future
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complete_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    issues: Mapped[list["Issue"]] = relationship(back_populates="sprint")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jira_key: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. ZTAEX-123
    jira_id: Mapped[str] = mapped_column(String(50), unique=True)
    issue_type: Mapped[str] = mapped_column(String(50))  # Bug, Story, Task, Sub-task
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str | None] = mapped_column(String(50))
    assignee_name: Mapped[str | None] = mapped_column(String(255))
    assignee_account_id: Mapped[str | None] = mapped_column(String(255))
    story_points: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository_id: Mapped[int | None] = mapped_column(ForeignKey("repositories.id"))
    sprint_id: Mapped[int | None] = mapped_column(ForeignKey("sprints.id"))

    repository: Mapped["Repository | None"] = relationship(back_populates="issues")
    sprint: Mapped["Sprint | None"] = relationship(back_populates="issues")
    transitions: Mapped[list["IssueTransition"]] = relationship(back_populates="issue")
    time_logs: Mapped[list["TimeLog"]] = relationship(back_populates="issue")
    pull_requests: Mapped[list["PullRequest"]] = relationship(back_populates="issue")
    cycle_metrics: Mapped["IssueCycleMetrics | None"] = relationship(back_populates="issue")


class IssueTransition(Base):
    __tablename__ = "issue_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"))
    from_status: Mapped[str | None] = mapped_column(String(100))
    to_status: Mapped[str] = mapped_column(String(100))
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    author_account_id: Mapped[str | None] = mapped_column(String(255))

    issue: Mapped["Issue"] = relationship(back_populates="transitions")


class TimeLog(Base):
    __tablename__ = "time_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"))
    author_account_id: Mapped[str | None] = mapped_column(String(255))
    time_spent_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    issue: Mapped["Issue"] = relationship(back_populates="time_logs")


# ── GitHub + git-ai entities ──────────────────────────────────────────


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_pr_id: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(50))  # open, closed, merged
    head_branch: Mapped[str] = mapped_column(String(500))
    base_branch: Mapped[str] = mapped_column(String(500))
    additions: Mapped[int | None] = mapped_column(Integer)
    deletions: Mapped[int | None] = mapped_column(Integer)
    review_comments_count: Mapped[int | None] = mapped_column(Integer, default=0)
    ai_lines_added: Mapped[int | None] = mapped_column(Integer, default=0)
    ai_lines_removed: Mapped[int | None] = mapped_column(Integer, default=0)
    ai_percentage: Mapped[float | None] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_review_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"))

    __table_args__ = (UniqueConstraint("repository_id", "number", name="uq_repo_pr_number"),)

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")
    issue: Mapped["Issue | None"] = relationship(back_populates="pull_requests")
    commits: Mapped[list["Commit"]] = relationship(back_populates="pull_request")
    review_comments: Mapped[list["ReviewComment"]] = relationship(back_populates="pull_request")
    quality_metrics: Mapped["AIQualityMetrics | None"] = relationship(back_populates="pull_request")
    webex_messages: Mapped[list["WebexMessage"]] = relationship(back_populates="pull_request")


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sha: Mapped[str] = mapped_column(String(40), unique=True)
    message: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    additions: Mapped[int | None] = mapped_column(Integer)
    deletions: Mapped[int | None] = mapped_column(Integer)

    # git-ai stats fields (from `git ai stats <sha> --json`)
    human_additions: Mapped[int | None] = mapped_column(Integer)
    ai_additions: Mapped[int | None] = mapped_column(Integer)
    mixed_additions: Mapped[int | None] = mapped_column(Integer)
    ai_accepted: Mapped[int | None] = mapped_column(Integer)
    total_ai_additions: Mapped[int | None] = mapped_column(Integer)
    total_ai_deletions: Mapped[int | None] = mapped_column(Integer)
    time_waiting_for_ai_secs: Mapped[int | None] = mapped_column(Integer)
    tool_model_breakdown: Mapped[str | None] = mapped_column(Text)

    pull_request_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id"))

    pull_request: Mapped["PullRequest | None"] = relationship(back_populates="commits")
    ai_attributions: Mapped[list["AIAttribution"]] = relationship(back_populates="commit")


class AIAttribution(Base):
    __tablename__ = "ai_attributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("commits.id"))
    file_path: Mapped[str] = mapped_column(String(1000))
    ai_lines_start: Mapped[int] = mapped_column(Integer)
    ai_lines_end: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_id: Mapped[str | None] = mapped_column(String(255))
    human_author: Mapped[str | None] = mapped_column(String(255))
    accepted_lines: Mapped[int | None] = mapped_column(Integer)
    overridden_lines: Mapped[int | None] = mapped_column(Integer)
    messages_url: Mapped[str | None] = mapped_column(String(1000))
    raw_note: Mapped[str | None] = mapped_column(Text)

    commit: Mapped["Commit"] = relationship(back_populates="ai_attributions")


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_comment_id: Mapped[int] = mapped_column(Integer, unique=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"))
    author: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    line_number: Mapped[int | None] = mapped_column(Integer)
    is_on_ai_code: Mapped[bool | None] = mapped_column(Boolean)  # enriched by B7
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str | None] = mapped_column(String(50))  # commented, approved, changes_requested
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pull_request: Mapped["PullRequest"] = relationship(back_populates="review_comments")


# ── Webex entities ─────────────────────────────────────────────────────


class WebexMessage(Base):
    __tablename__ = "webex_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webex_message_id: Mapped[str] = mapped_column(String(255), unique=True)
    room_id: Mapped[str] = mapped_column(String(255))
    person_id: Mapped[str] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    parent_message_id: Mapped[str | None] = mapped_column(String(255))  # thread parent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    pull_request_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id"))

    pull_request: Mapped["PullRequest | None"] = relationship(back_populates="webex_messages")


# ── Computed / materialized entities ───────────────────────────────────


class IssueCycleMetrics(Base):
    __tablename__ = "issue_cycle_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), unique=True)
    coding_time_hours: Mapped[float | None] = mapped_column(Float)
    review_time_hours: Mapped[float | None] = mapped_column(Float)
    waiting_time_hours: Mapped[float | None] = mapped_column(Float)
    total_cycle_time_hours: Mapped[float | None] = mapped_column(Float)
    is_ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_percentage: Mapped[float | None] = mapped_column(Float)
    review_rounds: Mapped[int | None] = mapped_column(Integer)
    ai_accepted_ratio: Mapped[float | None] = mapped_column(Float)
    total_time_waiting_for_ai_secs: Mapped[int | None] = mapped_column(Integer)
    primary_tool: Mapped[str | None] = mapped_column(String(100))
    ai_comment_density: Mapped[float | None] = mapped_column(Float)
    human_comment_density: Mapped[float | None] = mapped_column(Float)
    webex_response_time_hours: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    issue: Mapped["Issue"] = relationship(back_populates="cycle_metrics")


class AIQualityMetrics(Base):
    __tablename__ = "ai_quality_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), unique=True)
    ai_lines_unchanged: Mapped[int | None] = mapped_column(Integer)
    ai_lines_modified: Mapped[int | None] = mapped_column(Integer)
    unmodified_ai_ratio: Mapped[float | None] = mapped_column(Float)
    ai_review_blind_accepts: Mapped[int | None] = mapped_column(Integer)
    ai_review_total_threads: Mapped[int | None] = mapped_column(Integer)
    followup_fixes_24h: Mapped[int | None] = mapped_column(Integer)
    test_lines_added: Mapped[int | None] = mapped_column(Integer)
    has_tests_for_ai_code: Mapped[bool | None] = mapped_column(Boolean)
    total_time_waiting_for_ai_secs: Mapped[int | None] = mapped_column(Integer)
    reverted_within_7d: Mapped[bool | None] = mapped_column(Boolean)
    defect_linked: Mapped[bool | None] = mapped_column(Boolean)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    pull_request: Mapped["PullRequest"] = relationship(back_populates="quality_metrics")

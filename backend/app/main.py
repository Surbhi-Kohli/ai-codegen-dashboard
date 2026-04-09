import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.db.models import Base
from app.routers import github_webhooks, gitai_webhooks, dashboard
from app.config import settings

logger = logging.getLogger(__name__)

# Background tasks for polling
_jira_poll_task: asyncio.Task | None = None
_github_poll_task: asyncio.Task | None = None


async def jira_poll_loop():
    """Background loop that polls Jira at configured intervals."""
    from app.ingestion.jira_poller import poll_all_projects

    interval = settings.jira_poll_interval_minutes * 60
    logger.info(f"Starting Jira poller (every {settings.jira_poll_interval_minutes} min)")

    while True:
        try:
            if settings.jira_api_token:
                await poll_all_projects()
                logger.info("Jira poll completed")
            else:
                logger.debug("Jira polling skipped (no API token configured)")
        except Exception as e:
            logger.exception(f"Jira poll failed: {e}")

        await asyncio.sleep(interval)


async def github_poll_loop():
    """Background loop that polls GitHub at configured intervals."""
    from app.ingestion.github_poller import poll_all_repos

    interval = settings.jira_poll_interval_minutes * 60  # Same interval as Jira
    logger.info(f"Starting GitHub poller (every {settings.jira_poll_interval_minutes} min)")

    while True:
        try:
            if settings.github_token:
                await poll_all_repos()
                logger.info("GitHub poll completed")
            else:
                logger.debug("GitHub polling skipped (no token configured)")
        except Exception as e:
            logger.exception(f"GitHub poll failed: {e}")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _jira_poll_task, _github_poll_task

    # Create tables on startup (use alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start background polling tasks
    _jira_poll_task = asyncio.create_task(jira_poll_loop())
    _github_poll_task = asyncio.create_task(github_poll_loop())

    yield

    # Cleanup
    for task in [_jira_poll_task, _github_poll_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    await engine.dispose()


app = FastAPI(
    title="AI Codegen Dashboard",
    description="Backend ingestion and API for the AI Codegen Metrics Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github_webhooks.router, prefix="/webhooks/github", tags=["GitHub Webhooks"])
app.include_router(gitai_webhooks.router, prefix="/webhooks/gitai", tags=["git-ai Webhooks"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard API"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sync/jira")
async def sync_jira(background_tasks: BackgroundTasks):
    """Manually trigger a Jira sync."""
    from app.ingestion.jira_poller import poll_all_projects

    if not settings.jira_api_token:
        return {
            "status": "skipped",
            "reason": "No Jira API token configured. Set JIRA_API_TOKEN in .env",
            "projects": settings.jira_project_key_list,
        }

    background_tasks.add_task(poll_all_projects)
    return {
        "status": "started",
        "projects": settings.jira_project_key_list,
        "message": "Jira sync started in background",
    }


@app.post("/sync/github")
async def sync_github(background_tasks: BackgroundTasks):
    """Manually trigger a GitHub sync."""
    from app.ingestion.github_poller import poll_all_repos

    if not settings.github_token:
        return {
            "status": "skipped",
            "reason": "No GitHub token configured. Set GITHUB_TOKEN in .env",
            "repos": [f"{settings.github_org}/{r}" for r in settings.github_repo_list],
        }

    background_tasks.add_task(poll_all_repos)
    return {
        "status": "started",
        "repos": [f"{settings.github_org}/{r}" for r in settings.github_repo_list],
        "message": "GitHub sync started in background",
    }


@app.post("/sync/enrich")
async def sync_enrich(background_tasks: BackgroundTasks):
    """Manually trigger all enrichment tasks (linking, correlation, metrics)."""
    from app.enrichment.issue_pr_linker import link_unlinked_prs
    from app.enrichment.ai_code_correlator import correlate_all_untagged
    from app.enrichment.cycle_metrics import recompute_all
    from app.db.session import async_session

    async def run_enrichment():
        async with async_session() as db:
            linked = await link_unlinked_prs(db)
            correlated = await correlate_all_untagged(db)
            metrics = await recompute_all(db)
            await db.commit()
            return {"linked_prs": linked, "correlated_comments": correlated, "metrics_computed": metrics}

    background_tasks.add_task(run_enrichment)
    return {
        "status": "started",
        "message": "Running: PR↔Issue linking, AI code correlation, cycle metrics",
    }


@app.get("/sync/status")
async def sync_status():
    """Get current sync configuration status."""
    return {
        "jira": {
            "configured": bool(settings.jira_api_token),
            "base_url": settings.jira_base_url,
            "projects": settings.jira_project_key_list,
            "poll_interval_minutes": settings.jira_poll_interval_minutes,
        },
        "github": {
            "configured": bool(settings.github_token),
            "org": settings.github_org,
            "repos": settings.github_repo_list,
            "poll_interval_minutes": settings.jira_poll_interval_minutes,
        },
        "gitai": {
            "webhook_configured": bool(settings.gitai_webhook_secret),
            "hook_installed": True,  # We installed post-commit hook
        },
    }

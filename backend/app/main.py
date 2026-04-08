from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.db.models import Base
from app.routers import github_webhooks, gitai_webhooks, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Codegen Dashboard",
    description="Backend ingestion and API for the AI Codegen Metrics Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github_webhooks.router, prefix="/webhooks/github", tags=["GitHub Webhooks"])
app.include_router(gitai_webhooks.router, prefix="/webhooks/gitai", tags=["git-ai Webhooks"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard API"])


@app.get("/health")
async def health():
    return {"status": "ok"}

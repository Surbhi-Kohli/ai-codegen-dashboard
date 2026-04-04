# AI Codegen Dashboard — Backend

Backend ingestion and API service for the AI Codegen Metrics Dashboard.

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  Jira Poller │  │ GitHub Hooks │  │ git-ai Hooks │
│  (B2)        │  │ (B3)         │  │ (B4)         │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────────┬────┴────────┬────────┘
                    ▼             ▼
              ┌──────────┐  ┌──────────────┐
              │ Postgres │◄─│ Enrichment   │
              │ Database │  │ Engine       │
              │ (B1)     │  │ (B6-B9)      │
              └────┬─────┘  └──────────────┘
                   │
              ┌────▼─────┐
              │ Dashboard │
              │ API (B11) │
              └──────────┘
```

## Quick Start

### 1. Prerequisites
- Python 3.12+
- No database server needed (SQLite by default)

### 2. Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Jira/GitHub credentials (DB works out of the box)
```

### 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

That's it. Tables are auto-created in `ai_dashboard.db` (SQLite file) on first startup.
Visit `http://localhost:8000/docs` for the interactive API docs.

### 4. Database options

| Option | DATABASE_URL | When to use |
|--------|-------------|-------------|
| **SQLite** (default) | `sqlite+aiosqlite:///./ai_dashboard.db` | Hackathon / local dev — zero setup |
| **DDI MySQL** | `mysql+aiomysql://root:@localhost:3306/ai_dashboard` | Using existing Duo infra (`pip install aiomysql`) |
| **Postgres** | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_dashboard` | Standalone production (`pip install asyncpg`) |

### 5. Register webhooks

**GitHub:** Configure a webhook on your repo pointing to `https://<your-host>/webhooks/github/`
- Events: `pull_request`, `pull_request_review`, `pull_request_review_comment`, `push`
- Secret: matches `GITHUB_WEBHOOK_SECRET` in `.env`

**git-ai:** Configure git-ai post-push hook to POST to `https://<your-host>/webhooks/gitai/`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/webhooks/github/` | GitHub webhook receiver |
| POST | `/webhooks/gitai/` | git-ai attribution receiver |
| POST | `/webhooks/gitai/backfill` | Bulk historical backfill |
| GET | `/api/overview` | Overview KPIs |
| GET | `/api/delivery` | Delivery speed metrics |
| GET | `/api/bottlenecks` | Bottleneck analysis |
| GET | `/api/ai-impact` | AI impact metrics |
| GET | `/api/ai-quality` | AI quality & oversight |
| GET | `/api/issues/{jira_key}` | Issue drill-down |

All `/api/*` endpoints support `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` filters.

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Settings from env vars
│   ├── db/
│   │   ├── models.py                    # SQLAlchemy ORM models (B1)
│   │   └── session.py                   # Async DB session
│   ├── routers/
│   │   ├── github_webhooks.py           # GitHub webhook handler (B3)
│   │   ├── gitai_webhooks.py            # git-ai webhook handler (B4)
│   │   └── dashboard.py                 # Dashboard API endpoints (B11)
│   ├── ingestion/
│   │   └── jira_poller.py               # Jira polling service (B2)
│   └── enrichment/
│       ├── issue_pr_linker.py           # Issue ↔ PR linking (B6)
│       ├── ai_code_correlator.py        # Review comment ↔ AI code (B7)
│       ├── cycle_metrics.py             # IssueCycleMetrics engine (B8)
│       └── quality_metrics.py           # AIQualityMetrics engine (B9)
├── requirements.txt
├── .env.example
└── README.md
```

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    # Default: SQLite for zero-setup hackathon use. No server/credentials needed.
    # For production with Duo infra, switch to MySQL:
    #   database_url: str = "mysql+aiomysql://root:@localhost:3306/ai_dashboard"
    database_url: str = "sqlite+aiosqlite:///./ai_dashboard.db"

    # Jira
    jira_base_url: str = "https://cisco-sbg.atlassian.net"
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_keys: str = "ZTAEX,ZTCE"
    jira_poll_interval_minutes: int = 15

    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""
    github_org: str = "cisco-sbg"
    github_repos: str = "ZT-trustedpath"

    # git-ai
    gitai_webhook_secret: str = ""

    # Webex (stretch)
    webex_bot_token: str = ""
    webex_webhook_secret: str = ""
    webex_review_room_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def jira_project_key_list(self) -> list[str]:
        return [k.strip() for k in self.jira_project_keys.split(",") if k.strip()]

    @property
    def github_repo_list(self) -> list[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]


settings = Settings()

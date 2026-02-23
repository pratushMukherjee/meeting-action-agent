from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meeting_agent"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/meeting_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Jira
    jira_server_url: str = ""
    jira_user_email: str = ""
    jira_api_token: str = ""
    jira_default_project: str = "MEET"

    # Google
    google_credentials_file: str = "credentials/google_credentials.json"
    google_token_file: str = "credentials/google_token.json"

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "meeting-action-agent"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    max_retries: int = 3
    max_agent_steps: int = 20
    confidence_threshold: float = 0.7
    max_token_budget: int = 10000
    allowed_email_domains: str = "company.com"

    @property
    def allowed_domains_list(self) -> list[str]:
        return [d.strip() for d in self.allowed_email_domains.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

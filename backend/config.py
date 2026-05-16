from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    POSTGRES_HOST: str = Field(..., description="Required — Docker service hostname, e.g. postgres")
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "supplier_agent_db"
    POSTGRES_USER: str = "mypes_user"
    POSTGRES_PASSWORD: str = "changeme"

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"

    # PDF output (Docker: /app/generated_pos; local tests may override)
    GENERATED_POS_DIR: str = "/app/generated_pos"

    # External catalog search
    EXTERNAL_SEARCH_ENABLED: bool = True
    EXTERNAL_SEARCH_DEFAULT_LIMIT: int = 10
    EXTERNAL_SEARCH_CACHE_TTL_HOURS: int = 6
    EXTERNAL_SEARCH_GLOBAL_TIMEOUT: int = 20

    # Optional adapter credentials (CatalogSource.auth wins over these)
    AMAZON_PAAPI_ACCESS_KEY: str = ""
    AMAZON_PAAPI_SECRET_KEY: str = ""
    AMAZON_PAAPI_PARTNER_TAG: str = ""
    EBAY_OAUTH_TOKEN: str = ""
    ALIBABA_APP_KEY: str = ""
    ALIBABA_APP_SECRET: str = ""

    @property
    def prompts_dir(self) -> Path:
        backend_dir = Path(__file__).resolve().parent
        repo_prompts = backend_dir.parent / "prompts"
        if repo_prompts.is_dir():
            return repo_prompts
        return Path("/prompts")

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://evaldock:evaldock@localhost:5492/evaldock"
    app_key: str = ""
    allowed_target_origins: str = ""
    public_origin: str = "http://localhost:5188"
    cookie_secure: bool = False
    artifact_dir: str = "artifacts"
    demo_password: str = ""
    sample_origin: str = "http://samples:8090"
    max_response_bytes: int = 2_000_000
    session_hours: int = 24

    @property
    def queue_url(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def settings() -> Settings:
    return Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PO Sync Digest"
    version: str = "0.1.0"
    database_url: str = "sqlite:///./app.db"  # override via env for Postgres
    sov_url: str = "http://localhost:8765"
    sov_api_key: str = ""


settings = Settings()

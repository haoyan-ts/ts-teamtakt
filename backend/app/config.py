from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str
    SECRET_KEY: str
    AZURE_TENANT_ID: str
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    AZURE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    AZURE_MS365_CONNECT_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/ms365/callback"
    FRONTEND_URL: str = "http://localhost:5173"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ADMIN_EMAIL: str | None = None
    # Required in non-local environments; app refuses to start if unset or weak
    ADMIN_PASSWORD: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = None
    GITHUB_TOKEN: str | None = None


settings = Settings()  # type: ignore[call-arg]  # env vars injected by pydantic-settings

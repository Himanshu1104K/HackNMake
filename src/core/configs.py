from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Learning Project"
    description: str = "Learning Project API"
    version: str = "1.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    cors_origins: list[str] = ["*"]

    OPENAI_API_KEY: str
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DATA_EXPIRY_SECONDS: int = 60 * 60 * 24  # 1 day
    database_url: str = (
        "postgresql://heyova:HackMake1@learning-scalling.postgres.database.azure.com:5432/postgres?sslmode=require"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


settings = Settings()

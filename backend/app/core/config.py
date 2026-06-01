import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "智能骨科康复伴侣 API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./rehab_mvp.db")
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost,http://127.0.0.1,http://localhost:3000,http://127.0.0.1:3000",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()

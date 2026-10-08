"""App configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Core
    SECRET_KEY: str = "dev-secret-change-in-production"
    APP_ENV: str = "development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Invite codes
    INVITE_CODES: str = "KCR2025,TENNIS,MODEL,KCRDEMO"

    # RapidAPI
    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "tennis-live-data.p.rapidapi.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def invite_codes_list(self) -> List[str]:
        return [c.strip() for c in self.INVITE_CODES.split(",") if c.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    demo_mode: bool = True
    database_url: str = "sqlite:///./finance_control_tower.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    demo_user: str = "Finance Admin"
    serve_frontend: bool = False

    openai_api_key: str = ""
    gemini_api_key: str = ""
    ai_provider: str = "mock"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    data_provider: str = "mock"

    ai_rate_limit_per_minute: int = 30

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_ai_provider(self) -> str:
        if self.ai_provider == "openai" and self.openai_api_key:
            return "openai"
        if self.ai_provider == "gemini" and self.gemini_api_key:
            return "gemini"
        if self.openai_api_key and self.ai_provider != "mock":
            return "openai"
        if self.gemini_api_key and self.ai_provider != "mock":
            return "gemini"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()

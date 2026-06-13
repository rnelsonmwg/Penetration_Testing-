from __future__ import annotations

import os
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Khepri Nyame"
    storage_dir: str = os.getenv("KHEPRI_STORAGE_DIR", ".khepri_data")
    default_provider: str = os.getenv("KHEPRI_DEFAULT_PROVIDER", "local-rule-based")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")


settings = Settings()

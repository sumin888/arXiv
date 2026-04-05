from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # openrouter | anthropic (env: LLM_PROVIDER)
    llm_provider: Literal["openrouter", "anthropic"] = "openrouter"

    openrouter_api_key: str = ""
    # Free-tier NVIDIA-hosted option on OpenRouter (change if unavailable — see openrouter.ai/models, filter :free)
    openrouter_model: str = "nvidia/nemotron-nano-9b-v2:free"
    openrouter_http_referer: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    sqlite_path: str | None = None

    vector_top_k: int = 40
    fts_top_k: int = 40
    context_chunks: int = 10
    rrf_k: int = 60

    chunk_size: int = 1200
    chunk_overlap: int = 180

    # Phase 3 — code execution
    e2b_api_key: str = ""

    # Phase 2 — optional GitHub auth for higher rate limits
    github_token: str = ""

    @property
    def db_path(self) -> Path:
        if self.sqlite_path:
            return Path(self.sqlite_path)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "arxiv_rag.db"


settings = Settings()

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/ragdb"
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 8          # candidates fetched before reranking
    rerank_top_k: int = 5   # kept after reranking
    history_turns: int = 6  # recent conversation messages sent to LLM
    min_confidence: float = 0.40  # below this max score → low-confidence warning
    embedding_model: str = "gemini-embedding-001"
    generation_model: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()

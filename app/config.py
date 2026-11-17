from pydantic_settings import BaseSettings
from typing import Literal
from functools import lru_cache
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=True)
    # ─── App ─────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Interviewer Platform"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ai_interviewer"
    SYNC_DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/ai_interviewer"

    # ─── Vector Store ─────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"

    # ─── LLM ──────────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["gemini", "openai", "huggingface", "groq"] = "gemini"
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OPENAI_MODEL: str = "gpt-4o"
    # Groq API — free tier, OpenAI-compatible (https://console.groq.com/keys)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    # HuggingFace Inference API settings (requires paid credits for most models)
    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    HUGGINGFACE_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ─── Voice ────────────────────────────────────────────────────────────
    WHISPER_MODEL_SIZE: Literal["tiny", "base", "small", "medium", "large"] = "base"
    ELEVENLABS_API_KEY: str = ""

    # ─── File Storage ─────────────────────────────────────────────────────
    S3_BUCKET: str = "ai-interviewer"
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin123"
    AWS_REGION: str = "us-east-1"

    # ─── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Email ────────────────────────────────────────────────────────────
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@ai-interviewer.com"

    # ─── CORS ─────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

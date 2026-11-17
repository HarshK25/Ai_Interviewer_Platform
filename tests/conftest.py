"""
conftest.py — sets required environment variables before any app module is imported.

This prevents the LLM client, ChromaDB, and database drivers from trying to
connect to real services during unit tests.
"""
import os
import sys

# ── Inject dummy env vars before any app import ───────────────────────────────
# These override whatever is (or isn't) in .env so unit tests run fully offline.
_TEST_ENV = {
    "LLM_PROVIDER": "gemini",
    "GOOGLE_API_KEY": "test-fake-google-key",
    "OPENAI_API_KEY": "test-fake-openai-key",
    "HUGGINGFACE_API_KEY": "test-fake-hf-key",
    "HUGGINGFACE_MODEL": "fake/model",
    "HUGGINGFACE_EMBEDDING_MODEL": "fake/embedding-model",
    "SECRET_KEY": "test-secret-key-for-pytest-only",
    "DATABASE_URL": "postgresql+asyncpg://postgres:test@localhost:5432/test_db",
    "SYNC_DATABASE_URL": "postgresql://postgres:test@localhost:5432/test_db",
    "REDIS_URL": "redis://localhost:6379/0",
    "CHROMA_PERSIST_DIR": "/tmp/test_chroma",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin123",
    "SENDGRID_API_KEY": "",
    "ELEVENLABS_API_KEY": "",
    # Disable LangSmith tracing — it tries to reach external servers which the
    # sandbox blocks, causing every async LLM call to hang indefinitely.
    "LANGCHAIN_TRACING_V2": "false",
    "LANGCHAIN_TRACING": "false",
    "LANGCHAIN_API_KEY": "fake-no-tracing",
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)

# Clear the lru_cache on settings so it picks up the test env vars
# (handles re-import across test sessions)
try:
    from app.config import get_settings
    get_settings.cache_clear()
except Exception:
    pass

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from app.config import settings


def get_embedding_model():
    """Return the configured embedding model (Gemini, OpenAI, or HuggingFace)."""
    if settings.LLM_PROVIDER == "gemini":
        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.GOOGLE_API_KEY,
        )
    if settings.LLM_PROVIDER == "huggingface":
        # HuggingFaceEmbeddings runs locally via sentence-transformers — no API key needed
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=settings.HUGGINGFACE_EMBEDDING_MODEL,
        )
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.OPENAI_API_KEY,
    )


class _LazyEmbeddingModel:
    """Lazy proxy — embedding model is only instantiated on first use."""

    def __init__(self):
        self._model = None

    def _get(self):
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def embed_documents(self, *args, **kwargs):
        return self._get().embed_documents(*args, **kwargs)

    def embed_query(self, *args, **kwargs):
        return self._get().embed_query(*args, **kwargs)


# Singleton — lazily initialised on first use
embedding_model = _LazyEmbeddingModel()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from app.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)


class _HuggingFaceDirectClient:
    """
    HuggingFace Inference API client using huggingface_hub.InferenceClient.

    Uses chat_completion() which routes through the provider that supports
    Mistral (novita), requiring the token to have 'Inference Providers' permission.
    NOTE: novita provider requires paid HF credits. Use LLM_PROVIDER=gemini or groq instead.
    """

    def __init__(self, model: str, token: str, temperature: float = 0.7, max_new_tokens: int = 1024):
        from huggingface_hub import InferenceClient
        self._client = InferenceClient(model=model, token=token)
        self._temperature = temperature
        self._max_new_tokens = max_new_tokens
        self._model = model

    def _generate(self, prompt: str) -> str:
        """Synchronous HF chat completion — uses novita provider for Mistral."""
        response = self._client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self._max_new_tokens,
            temperature=self._temperature,
        )
        return response.choices[0].message.content

    async def ainvoke(self, prompt, **kwargs):
        """Async wrapper — runs sync call in thread pool to avoid blocking."""
        from types import SimpleNamespace
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, lambda: self._generate(str(prompt)))
        logger.debug(f"HF response length: {len(text)} chars")
        return SimpleNamespace(content=text)

    def invoke(self, prompt, **kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(content=self._generate(str(prompt)))


def get_llm():
    """
    Return the configured LLM client based on LLM_PROVIDER setting.

    Supported providers:
      - gemini      : Google Gemini (free tier at aistudio.google.com) — RECOMMENDED
      - groq        : Groq API (free tier, OpenAI-compatible, very fast) — RECOMMENDED
      - openai      : OpenAI GPT (paid)
      - huggingface : HuggingFace Inference API (requires paid credits for Mistral)
    """
    provider = settings.LLM_PROVIDER
    logger.info(f"Initialising LLM provider: {provider}")

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7,
            convert_system_message_to_human=True,
        )

    if provider == "groq":
        # Groq uses an OpenAI-compatible API — no extra package needed.
        # Free tier: OTPM limit 1000 → keep max_tokens under 900.
        # Get a free key at https://console.groq.com/keys
        return ChatOpenAI(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.7,
            max_tokens=800,
        )

    if provider == "huggingface":
        return _HuggingFaceDirectClient(
            model=settings.HUGGINGFACE_MODEL,
            token=settings.HUGGINGFACE_API_KEY,
            temperature=0.7,
            max_new_tokens=1024,
        )

    # Default: OpenAI
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.7,
    )


class _LazyLLM:
    """
    Lazy proxy for the LLM singleton.

    The actual client is created on first access so that:
    - Unit tests can patch 'app.llm.llm_client.llm' before any real call is made.
    - The server does NOT attempt to validate the API key at import time.
    """

    def __init__(self):
        self._llm = None

    def _get(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    # Proxy the two methods used by the app (ainvoke / invoke)
    async def ainvoke(self, *args, **kwargs):
        result = await self._get().ainvoke(*args, **kwargs)
        # Normalize: ensure response always has .content
        if isinstance(result, str):
            from types import SimpleNamespace
            return SimpleNamespace(content=result)
        return result

    def invoke(self, *args, **kwargs):
        result = self._get().invoke(*args, **kwargs)
        if isinstance(result, str):
            from types import SimpleNamespace
            return SimpleNamespace(content=result)
        return result

    # Allow tests to replace the inner LLM directly
    def __setattr__(self, name, value):
        if name == "_llm":
            object.__setattr__(self, name, value)
        else:
            setattr(self._get(), name, value)


# Singleton — lazily initialised on first use
llm = _LazyLLM()

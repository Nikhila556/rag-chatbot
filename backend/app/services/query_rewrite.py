import asyncio
import logging
from google import genai
from google.genai import types
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM = (
    "You are a search query optimizer. "
    "Expand the user's question into a richer search query by adding synonyms, "
    "related terms, and alternative phrasings. "
    "Return ONLY the improved query text — no explanation, no quotes."
)


def _rewrite_sync(query: str) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            max_output_tokens=120,
        ),
    )
    return response.text.strip()


async def rewrite_query(query: str) -> str:
    """Return an expanded version of *query* for better retrieval coverage."""
    try:
        rewritten = await asyncio.to_thread(_rewrite_sync, query)
        logger.info("Query rewrite: %r -> %r", query[:60], rewritten[:80])
        return rewritten
    except Exception as e:
        logger.warning("Query rewrite failed (%s), using original", e)
        return query

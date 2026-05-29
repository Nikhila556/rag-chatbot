import asyncio
import logging
from google import genai
from google.genai import types
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE = 100        # Gemini batchEmbedContents supports up to 100 items
_MAX_CONCURRENT = 4     # parallel in-flight embedding requests


def _embed_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    client = genai.Client(api_key=settings.gemini_api_key)
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [e.values for e in result.embeddings]


async def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed texts in parallel batches, respecting the API concurrency limit."""
    batches = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async def embed_one(batch: list[str]) -> list[list[float]]:
        async with sem:
            return await asyncio.to_thread(_embed_batch, batch, task_type)

    results = await asyncio.gather(*[embed_one(b) for b in batches])
    embeddings = [vec for batch_result in results for vec in batch_result]
    logger.debug("Embedded %d texts in %d parallel batches", len(texts), len(batches))
    return embeddings


async def embed_query(query: str) -> list[float]:
    result = await asyncio.to_thread(_embed_batch, [query], "RETRIEVAL_QUERY")
    return result[0]

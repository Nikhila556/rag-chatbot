import asyncio
import json
import logging
import re
from google import genai
from google.genai import types
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM = (
    "You are a relevance ranker for a document retrieval system. "
    "Given a question and numbered chunks, output a JSON array of chunk indices "
    "ordered from most to least relevant to the question. "
    "Include ALL indices. Return ONLY the JSON array — e.g. [2, 0, 1, 3]."
)


def _rank_sync(query: str, chunks: list[dict]) -> list[int]:
    snippets = "\n\n".join(
        f"[{i}] {c['content'][:400]}" for i, c in enumerate(chunks)
    )
    prompt = f"Question: {query}\n\nChunks:\n{snippets}"
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=_SYSTEM),
    )
    text = response.text.strip()
    # Extract JSON array robustly
    m = re.search(r"\[[\d,\s]+\]", text)
    if not m:
        raise ValueError(f"Unexpected rerank response: {text!r}")
    return json.loads(m.group())


async def rerank_chunks(query: str, chunks: list[dict], top_n: int | None = None) -> list[dict]:
    """Reorder *chunks* by relevance to *query* using the LLM, keep top_n."""
    if len(chunks) <= 1:
        return chunks
    n = top_n or settings.rerank_top_k
    try:
        order = await asyncio.to_thread(_rank_sync, query, chunks)
        # Build reranked list, guarding against out-of-range indices
        reranked = [chunks[i] for i in order if 0 <= i < len(chunks)]
        # Append any chunks the LLM missed (shouldn't happen, but be safe)
        seen = set(order)
        reranked += [c for i, c in enumerate(chunks) if i not in seen]
        result = reranked[:n]
        logger.info("Reranked %d -> %d chunks for query %r", len(chunks), len(result), query[:50])
        return result
    except Exception as e:
        logger.warning("Reranking failed (%s), returning original order", e)
        return chunks[:n]

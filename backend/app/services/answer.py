import logging
import asyncio
from google import genai
from google.genai import types
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are a precise document assistant. Answer questions ONLY using the provided context chunks.
Rules:
- Cite sources inline using the exact label from the reference header, e.g. [Page 4, vitamins.pdf].
- If the context does not contain enough information to answer, respond with exactly: "I don't know based on the provided document."
- Do not speculate or use outside knowledge.
- Be concise and factual."""


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for chunk in chunks:
        page = chunk.get("page_number") or "?"
        doc = chunk.get("document_name", "unknown")
        # Use the wider context window for LLM input when available
        body = chunk.get("context") or chunk["content"]
        parts.append(f"[Page {page}, {doc}]\n{body}")
    return "\n\n---\n\n".join(parts)


def _build_history_text(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        # Truncate long assistant answers so history doesn't dominate the prompt
        body = msg["content"][:600] if msg["role"] == "assistant" else msg["content"]
        lines.append(f"{role}: {body}")
    return "Previous conversation:\n" + "\n".join(lines) + "\n\n"


def _generate(prompt: str) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text.strip()


async def generate_answer(
    query: str,
    chunks: list[dict],
    history: list[dict] | None = None,
) -> str:
    if not chunks:
        return "I don't know based on the provided document."

    context = _build_context(chunks)
    history_text = _build_history_text(history or [])
    prompt = f"{history_text}Context:\n{context}\n\nQuestion: {query}"
    answer = await asyncio.to_thread(_generate, prompt)
    logger.info("Generated answer (%d chars) from %d chunks", len(answer), len(chunks))
    return answer


def build_stream_prompt(
    query: str,
    chunks: list[dict],
    history: list[dict] | None = None,
) -> str:
    """Build the prompt string used for streaming (caller drives the generation)."""
    context = _build_context(chunks)
    history_text = _build_history_text(history or [])
    return f"{history_text}Context:\n{context}\n\nQuestion: {query}"

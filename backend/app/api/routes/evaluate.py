"""
Lightweight RAGAS-style evaluation endpoint.
Scores a question/answer/context triple using the LLM as judge.
"""
import asyncio
import json
import logging
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types
from ...core.database import get_db
from ...core.config import get_settings
from ...services.retrieval import retrieve_chunks
from ...services.answer import generate_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluate", tags=["evaluate"])
settings = get_settings()

_EVAL_SYSTEM = "You are an expert RAG evaluator. Respond ONLY with a JSON object."

_EVAL_PROMPT = """Evaluate the following RAG response.

Question: {question}

Retrieved Context:
{context}

Generated Answer: {answer}

Score each metric from 0.0 to 1.0:
- faithfulness: Does the answer stay within the provided context? (1.0 = completely grounded, 0.0 = hallucinated)
- answer_relevancy: How well does the answer address the question? (1.0 = fully answers, 0.0 = off-topic)
- context_relevancy: How relevant is the retrieved context to the question? (1.0 = highly relevant, 0.0 = irrelevant)

Respond with exactly this JSON (no markdown, no extra text):
{{"faithfulness": 0.0, "answer_relevancy": 0.0, "context_relevancy": 0.0}}"""


class EvaluateRequest(BaseModel):
    question: str
    document_id: str | None = None
    # If answer is provided, skip generation and evaluate the given answer
    answer: str | None = None


def _eval_sync(question: str, answer: str, context: str) -> dict:
    prompt = _EVAL_PROMPT.format(question=question, answer=answer, context=context[:3000])
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_EVAL_SYSTEM,
            max_output_tokens=128,
        ),
    )
    text = response.text.strip()
    # Extract JSON object robustly
    m = re.search(r"\{[^}]+\}", text)
    if not m:
        raise ValueError(f"Could not parse eval response: {text!r}")
    return json.loads(m.group())


@router.post("/")
async def evaluate(req: EvaluateRequest, db: AsyncSession = Depends(get_db)):
    doc_id = UUID(req.document_id) if req.document_id else None

    # Retrieve relevant chunks for the question
    chunks = await retrieve_chunks(req.question, db, document_id=doc_id)
    if not chunks:
        raise HTTPException(status_code=422, detail="No chunks retrieved — upload a document first")

    # Use provided answer or generate one
    answer = req.answer or await generate_answer(req.question, chunks)

    # Build context string for evaluation
    context = "\n\n---\n\n".join(
        f"[Page {c.get('page_number', '?')}, {c.get('document_name', 'unknown')}]\n{c['content']}"
        for c in chunks
    )

    try:
        scores = await asyncio.to_thread(_eval_sync, req.question, answer, context)
    except Exception as e:
        logger.error("Evaluation LLM call failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")

    # Ensure all expected keys exist and values are floats in [0, 1]
    result = {}
    for key in ("faithfulness", "answer_relevancy", "context_relevancy"):
        val = scores.get(key, 0.0)
        result[key] = max(0.0, min(1.0, float(val)))

    result["answer"] = answer
    result["chunks_used"] = len(chunks)
    logger.info("Evaluation scores for %r: %s", req.question[:50], result)
    return result

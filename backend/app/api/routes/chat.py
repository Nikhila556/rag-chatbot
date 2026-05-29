import asyncio
import json
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google import genai
from google.genai import types
from ...core.database import get_db
from ...core.config import get_settings
from ...models.chat import Conversation, Message
from ...models.document import Document
from ...services.retrieval import retrieve_chunks
from ...services.answer import generate_answer, build_stream_prompt, SYSTEM_PROMPT
from ...services.query_rewrite import rewrite_query
from ...services.rerank import rerank_chunks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    document_id: str | None = None
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_history(conv_id, db: AsyncSession) -> list[dict]:
    """Load last N message pairs from a conversation for context."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(settings.history_turns)
    )
    msgs = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs]


async def _resolve_or_create_conv(req: ChatRequest, db: AsyncSession):
    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == req.conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv
    doc_id = UUID(req.document_id) if req.document_id else None
    title = req.message[:60] + ("..." if len(req.message) > 60 else "")
    conv = Conversation(title=title, document_id=doc_id)
    db.add(conv)
    await db.flush()
    return conv


def _build_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "chunk_index": c["chunk_index"],
            "content": c["content"][:300],
            "score": c["score"],
            "page_number": c.get("page_number"),
            "document_name": c.get("document_name"),
        }
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# Standard (non-streaming) endpoint
# ---------------------------------------------------------------------------

@router.post("/")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    conv = await _resolve_or_create_conv(req, db)

    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)

    doc_id = conv.document_id or (UUID(req.document_id) if req.document_id else None)

    # Rewrite query and load history in parallel — they are independent
    search_query, history = await asyncio.gather(
        rewrite_query(req.message),
        _load_history(conv.id, db),
    )

    # Hybrid retrieval → rerank → generate
    chunks = await retrieve_chunks(search_query, db, document_id=doc_id)
    chunks = await rerank_chunks(req.message, chunks)
    answer = await generate_answer(req.message, chunks, history=history)

    sources = _build_sources(chunks)
    assistant_msg = Message(
        conversation_id=conv.id, role="assistant", content=answer, sources=sources
    )
    db.add(assistant_msg)
    await db.commit()

    return {
        "conversation_id": str(conv.id),
        "answer": answer,
        "sources": sources,
        "message_id": str(assistant_msg.id),
    }


# ---------------------------------------------------------------------------
# Streaming (SSE) endpoint
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    conv = await _resolve_or_create_conv(req, db)

    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)

    doc_id = conv.document_id or (UUID(req.document_id) if req.document_id else None)

    # Rewrite query and load history in parallel — they are independent
    search_query, history = await asyncio.gather(
        rewrite_query(req.message),
        _load_history(conv.id, db),
    )

    chunks = await retrieve_chunks(search_query, db, document_id=doc_id)
    chunks = await rerank_chunks(req.message, chunks)

    sources = _build_sources(chunks)
    prompt = build_stream_prompt(req.message, chunks, history=history)
    conv_id_str = str(conv.id)

    # Commit user message now so it's durable before we start streaming
    await db.commit()

    async def event_generator():
        # First event: metadata (conversation id + sources) so the UI can render them immediately
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv_id_str, 'sources': sources})}\n\n"

        full_answer = ""
        try:
            gen_client = genai.Client(api_key=settings.gemini_api_key)
            async for chunk in await gen_client.aio.models.generate_content_stream(
                model=settings.generation_model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            ):
                token = chunk.text or ""
                if token:
                    full_answer += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            logger.error("Streaming generation error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Persist assistant message after stream completes
        try:
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=full_answer.strip(),
                sources=sources,
            )
            db.add(assistant_msg)
            await db.commit()
            yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_msg.id)})}\n\n"
        except Exception as e:
            logger.error("Failed to persist streamed message: %s", e)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

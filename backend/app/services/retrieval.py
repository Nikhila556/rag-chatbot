import logging
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import get_settings
from .embedding import embed_query

logger = logging.getLogger(__name__)
settings = get_settings()

# RRF constant — lower = more weight on top ranks
_RRF_K = 60


async def retrieve_chunks(
    query: str,
    db: AsyncSession,
    document_id: UUID | None = None,
    top_k: int | None = None,
) -> list[dict]:
    k = top_k or settings.top_k
    k2 = k * 4  # wider candidate pool for each sub-search before fusion

    query_vec = await embed_query(query)
    vec_str = "[" + ",".join(map(str, query_vec)) + "]"

    doc_filter = "AND c.document_id = CAST(:doc_id AS uuid)" if document_id else ""

    # Hybrid search: vector similarity + PostgreSQL full-text (BM25-like ts_rank), fused with RRF
    sql = text(f"""
        WITH vector_search AS (
            SELECT c.id,
                   ROW_NUMBER() OVER (ORDER BY c.embedding <=> CAST(:vec AS vector)) AS rank
            FROM chunks c
            WHERE TRUE {doc_filter}
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :k2
        ),
        text_search AS (
            SELECT c.id,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(
                           to_tsvector('english', c.content),
                           plainto_tsquery('english', :query_text)
                       ) DESC
                   ) AS rank
            FROM chunks c
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query_text)
            {doc_filter}
            LIMIT :k2
        ),
        rrf AS (
            SELECT
                COALESCE(vs.id, ts.id) AS id,
                COALESCE(1.0 / (:rrf_k + vs.rank), 0.0) +
                COALESCE(1.0 / (:rrf_k + ts.rank), 0.0) AS rrf_score
            FROM vector_search vs
            FULL OUTER JOIN text_search ts ON vs.id = ts.id
        )
        SELECT c.id, c.document_id, c.chunk_index, c.content, c.context,
               c.page_number, d.original_filename,
               r.rrf_score,
               -- Cosine similarity (0–1) used for display and confidence; RRF only drives ordering
               1 - (c.embedding <=> CAST(:vec AS vector)) AS vector_score
        FROM rrf r
        JOIN chunks c ON r.id = c.id
        JOIN documents d ON c.document_id = d.id
        ORDER BY r.rrf_score DESC
        LIMIT :k
    """)

    params: dict = {"vec": vec_str, "query_text": query, "k2": k2, "k": k, "rrf_k": _RRF_K}
    if document_id:
        params["doc_id"] = str(document_id)

    rows = await db.execute(sql, params)

    results = []
    for row in rows.mappings():
        results.append({
            "id": str(row["id"]),
            "document_id": str(row["document_id"]),
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "context": row["context"],
            "page_number": row["page_number"],
            "document_name": row["original_filename"],
            # Cosine similarity (0–1): meaningful for display and confidence checks
            "score": float(row["vector_score"]) if row["vector_score"] is not None else 0.0,
            # RRF score kept internally (used by reranker fallback ordering)
            "rrf_score": float(row["rrf_score"]) if row["rrf_score"] is not None else 0.0,
        })

    logger.info(
        "Hybrid retrieval: query=%r | returned=%d (top_k=%d) | docs=%s | cosine=[%s]",
        query[:60],
        len(results),
        k,
        ",".join(sorted({r["document_name"] for r in results})),
        ",".join(f"{r['score']:.3f}" for r in results),
    )
    return results

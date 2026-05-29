import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ...core.database import get_db
from ...core.config import get_settings
from ...models.document import Document, Chunk
from ...services.ingestion import extract_text, split_into_chunks
from ...services.embedding import embed_texts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


async def _ingest_file(
    save_path: Path,
    original_filename: str,
    doc: Document,
    db: AsyncSession,
) -> int:
    """Extract, chunk, embed and store chunks for a document. Returns chunk count."""
    # 1. Run CPU-bound extraction off the event loop so it doesn't block other requests
    pages = await asyncio.to_thread(extract_text, str(save_path))

    # 2. Semantic chunking (fast, stays on thread)
    chunks = await asyncio.to_thread(
        split_into_chunks, pages, settings.chunk_size, settings.chunk_overlap
    )
    if not chunks:
        raise HTTPException(status_code=422, detail="Could not extract any text from the file")

    # 3. Compute hierarchical context window in memory — avoids a flush + UPDATE cycle later
    for i, chunk in enumerate(chunks):
        prev = chunks[i - 1]["content"] if i > 0 else ""
        nxt  = chunks[i + 1]["content"] if i < len(chunks) - 1 else ""
        chunk["context"] = "\n\n".join(filter(None, [prev, chunk["content"], nxt])).strip()

    # 4. Contextual embeddings: prepend document name so the vector carries document context
    texts_to_embed = [
        f"Document: {original_filename}\n\n{c['content']}" for c in chunks
    ]
    embeddings = await embed_texts(texts_to_embed)

    # 5. Bulk-insert all Chunk rows in one db.add_all() call — no intermediate flush needed
    db.add_all([
        Chunk(
            document_id=doc.id,
            chunk_index=i,
            content=c["content"],
            context=c["context"],
            page_number=c["page_number"],
            embedding=emb,
        )
        for i, (c, emb) in enumerate(zip(chunks, embeddings))
    ])

    return len(chunks)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    doc_id = uuid.uuid4()
    save_path = UPLOAD_DIR / f"{doc_id}{ext}"

    try:
        with save_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info("Saved upload: %s -> %s", file.filename, save_path)

        doc = Document(
            id=doc_id,
            filename=str(save_path),
            original_filename=file.filename,
            total_chunks=0,
        )
        db.add(doc)
        await db.flush()

        total = await _ingest_file(save_path, file.filename, doc, db)
        doc.total_chunks = total
        await db.commit()

        logger.info("Ingested %s: %d chunks", file.filename, total)
        return {"id": str(doc_id), "filename": file.filename, "total_chunks": total}

    except HTTPException:
        await db.rollback()
        if save_path.exists():
            save_path.unlink()
        raise
    except Exception as e:
        await db.rollback()
        if save_path.exists():
            save_path.unlink()
        logger.error("Failed to ingest %s: %s", file.filename, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{document_id}/reingest")
async def reingest_document(
    document_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Replace a document's file and re-process all its chunks."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    new_path = UPLOAD_DIR / f"{document_id}{ext}"

    try:
        # Delete old file and chunks
        old_path = Path(doc.filename)
        if old_path.exists():
            old_path.unlink()
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

        # Save new file
        with new_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        doc.filename = str(new_path)
        doc.original_filename = file.filename
        doc.summary = None
        await db.flush()

        total = await _ingest_file(new_path, file.filename, doc, db)
        doc.total_chunks = total
        await db.commit()

        logger.info("Re-ingested %s: %d chunks", file.filename, total)
        return {"id": document_id, "filename": file.filename, "total_chunks": total}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to re-ingest %s: %s", file.filename, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.original_filename,
            "total_chunks": d.total_chunks,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{document_id}")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pdf_path = Path(doc.filename)
    if pdf_path.exists():
        pdf_path.unlink()

    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}

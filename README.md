# RAG Chatbot

A production-grade Retrieval-Augmented Generation (RAG) system with a real-time streaming chat UI. Upload PDFs, DOCX, or TXT files and ask questions grounded in your documents — answers cite exact page numbers.

## Architecture

```
Frontend (React + Vite + Tailwind)
    ↕ SSE streaming / REST
Backend (FastAPI + async Python)
    ├── Ingest:   PyMuPDF / python-docx  (PDF/DOCX/TXT → text + tables)
    ├── Chunk:    Semantic chunking (header-aware, paragraph boundaries, 800 chars / 150 overlap)
    ├── Embed:    Gemini gemini-embedding-001  (3072-dim vectors)
    ├── Store:    PostgreSQL + pgvector
    ├── Search:   Hybrid (vector cosine + BM25 full-text) fused with RRF
    ├── Rerank:   LLM cross-encoder reranking (top 8 → top 5)
    └── Answer:   Gemini gemini-2.5-flash  (streamed, grounded, with citations)
```

## Features

- 📄 Upload PDF, DOCX, DOC, TXT files
- 💬 Real-time streaming answers (SSE) — see responses as they're generated
- 📌 Inline citations with page numbers: `[Page 52, nutrition.pdf]`
- 🔍 Hybrid search: semantic (vector) + keyword (BM25) combined with Reciprocal Rank Fusion
- 🤖 LLM-based reranking for better relevance
- 🔄 Query rewriting — expands your question with synonyms before searching
- 📚 Multi-document support — ask across all documents or scope to one
- 🗂️ Persistent conversation history with sidebar navigation
- ⚠️ Low-confidence warnings when chunks score below threshold

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL + pgvector)
- Python 3.11+
- Node.js 18+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

## Quick Start

### 1. Start the database

```bash
docker compose up -d
```

### 2. Set up the backend

```bash
cd backend
cp .env.example .env
# Edit .env — set GEMINI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## Usage

1. **Upload** a PDF, DOCX, or TXT file using the drop zone in the bottom-left sidebar.
2. **Select a document** from the sidebar to scope questions to that file, or keep **All documents** selected to search across everything.
3. **Ask a question** — the answer streams in real time with inline page citations.
4. **Expand sources** below each answer to see the exact chunks that were retrieved.
5. **Previous chats** are saved and accessible from the sidebar.

## Design Decisions

| Concern | Choice | Why |
|---|---|---|
| PDF extraction | PyMuPDF (fitz) | Fast, handles tables (converted to markdown), no external API needed |
| Chunking | Semantic (header + paragraph aware) | Keeps sections together; never cuts mid-sentence |
| Embeddings | `gemini-embedding-001` (3072-dim) | Highest quality in Gemini family |
| Vector store | PostgreSQL + pgvector | Single service; SQL + vector in one place |
| Search | Hybrid vector + BM25 + RRF | Vector finds synonyms; BM25 finds exact terms; RRF combines ranks |
| Reranking | LLM cross-encoder | Re-scores top-8 candidates for true relevance; falls back to original order on failure |
| Query rewriting | Gemini LLM | Expands short queries with synonyms and related terms before retrieval |
| Streaming | FastAPI SSE + async generator | Word-by-word streaming; user sees answer as it's generated |
| Chunk context | prev + self + next window | LLM reads wider context; chunked index stays small |
| Answer model | `gemini-2.5-flash` | Fast, cheap, strong instruction following for grounded citation |

## Environment Variables

```env
GEMINI_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/ragdb   # optional override
```

## Project Structure

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── core/           # config, database
│   │   ├── models/         # SQLAlchemy models (Document, Chunk, Conversation, Message)
│   │   ├── services/       # ingestion, embedding, retrieval, rerank, answer, query_rewrite
│   │   └── api/routes/     # documents, chat (streaming), history
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/     # ChatPanel, ChatMessage, Sidebar, UploadZone
│       ├── App.tsx
│       └── api.ts
└── docker-compose.yml
```

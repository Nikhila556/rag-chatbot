# RAG System

A minimal Retrieval-Augmented Generation (RAG) system with a polished chat UI. Upload a PDF, then ask questions grounded in the document — answers cite specific chunks.

## Architecture

```
Frontend (React + Vite + Tailwind)
    ↕ HTTP
Backend (FastAPI)
    ├── Ingest:  Gemini 1.5 Flash (PDF → clean text)
    ├── Embed:   Gemini text-embedding-004 (768-dim)
    ├── Store:   PostgreSQL + pgvector
    └── Answer:  Gemini 1.5 Flash (grounded, with citations)
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres + pgvector)
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
# Edit .env and set your GEMINI_API_KEY
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

1. Upload a PDF using the drop zone in the sidebar.
2. Click the document name to scope queries to that file.
3. Type a question in the chat box — the answer will cite the chunks used.
4. Previous chats are persisted and viewable in the sidebar.

## Design Decisions

| Concern | Choice | Why |
|---------|--------|-----|
| PDF extraction | Gemini 1.5 Flash | Handles scanned PDFs, tables, images; no local dependencies |
| Embeddings | `text-embedding-004` (768-dim) | Best quality in Gemini family; consistent dimensionality |
| Vector store | Postgres + pgvector | Single service; SQL + vector in one place; easy to scale |
| Chunk size | 800 chars / 150 overlap | Balances context richness vs. embedding precision |
| Answer model | Gemini 1.5 Flash | Fast and cheap; strong instruction following for citation |

## Limitations / Next Steps

- Single-file ingest (multi-file per conversation not yet supported)
- No auth / multi-user isolation
- Chunk splitting is character-based; semantic splitting would improve precision
- No reranker — a cross-encoder rerank step would improve top-k quality
- Streaming responses not yet implemented

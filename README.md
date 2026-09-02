# Chatbot — Local AI Assistant & Document Intelligence

A local-first, privacy-focused AI assistant built with **React + TypeScript + Vite** on the frontend, **FastAPI + Pydantic v2 + SQLite** on the backend, and **Ollama** serving **Gemma 4 E4B** with **nomic-embed-text** local embeddings.

---

## Architecture Overview

```
User Message (+ Attachments)
     ↓
FastAPI Backend (/api/chat)
     ↓
Just-In-Time (JIT) Indexing (if unindexed)
     ↓
Local Embeddings (nomic-embed-text, 768-dim)
     ↓
Local SQLite Vector Store (Cosine Similarity Search)
     ↓
Two-Stage Candidate Selection & Deduplication
     ↓
Prompt Grounding & Anti-Injection Guardrails
     ↓
Ollama (Gemma 4 E4B) — SSE Token Streaming
     ↓
React UI — Stream Rendering & Citation Provenance
```

---

## Key Capabilities

- **Document Processing Engine**: Native structured text and section extraction for `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, and `.json`.
- **Intelligent Chunking**: Natural boundary-aware chunking preserving section hierarchy, page numbers, and source provenance.
- **Local Dense Embeddings**: 768-dimensional dense vectors generated locally via Ollama (`nomic-embed-text`).
- **Persistent SQLite Vector Store**: High-performance binary float32 vector storage and fast cosine similarity retrieval with attachment isolation.
- **Just-In-Time (JIT) Indexing**: Automatic, idempotent on-demand document indexing upon first query with per-attachment concurrency safety.
- **Evidence-First Grounded RAG**: Context construction with structured provenance (`=== SOURCE N ===`), multi-document comparison guidance, and standard abstention for absent facts.
- **Prompt-Injection Defense**: Reference documents are strictly isolated as passive data (`UNTRUSTED DATA`).
- **Evaluation & Benchmark Framework**: 30-case repeatable benchmark dataset with pure deterministic metrics measuring retrieval hit rate, recall, precision, MRR, fact coverage, groundedness, and latencies.

---

## Project Structure

```
Chatbot/
├── frontend/                  # React 19 + TypeScript + Vite + Tailwind CSS v4
│   ├── src/
│   │   ├── components/        # UI components (AppShell, Sidebar, Workspace, Composer, Chips)
│   │   ├── hooks/             # Custom hooks (useChat state & stream batching)
│   │   ├── services/          # Backend API, File upload & SSE stream client
│   │   └── types/             # TypeScript type definitions
│   ├── package.json           # Frontend dependencies
│   └── vite.config.ts         # Vite bundler & /api proxy configuration
│
├── backend/                   # FastAPI Python backend
│   ├── app/
│   │   ├── evaluation/        # Benchmark dataset, evaluator, runner, corpus & tests
│   │   ├── models/            # Pydantic v2 schemas (chat, document, embedding, file, retrieval)
│   │   ├── routes/            # API endpoints (/api/chat, /api/files/*, /api/search, /api/model, /api/health)
│   │   ├── services/          # RAG, Document Processor, Chunker, Embedding, Vector Store, Ollama
│   │   ├── config.py          # Centralized Pydantic v2 settings
│   │   └── main.py            # FastAPI entry point & CORS configuration
│   ├── storage/               # Local runtime data (uploads/, vector_store/vectors.db)
│   └── requirements.txt       # Python dependencies
│
├── evaluation/
│   └── results/               # Preserved benchmark reports (baseline.json, optimized.json, grounded.json)
│
├── .env.example               # Example environment configuration
├── .gitignore                 # Repository exclusion rules
└── README.md                  # Project documentation
```

---

## Prerequisites

1. **Ollama**: Ensure [Ollama](https://ollama.com) is installed with the required models:
   ```bash
   ollama pull gemma4:e4b
   ollama pull nomic-embed-text
   ollama serve
   ```
2. **Node.js**: Node 18+ (Node 20+ recommended)
3. **Python**: Python 3.10+

---

## Getting Started

### 1. Backend Setup

```bash
cd backend

# Create & activate virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend runs on `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend runs on `http://localhost:5173`. Requests to `/api/*` are proxied to `http://127.0.0.1:8000`.

---

## API Endpoints Reference

### Chat & Model
- `POST /api/chat` — Server-Sent Events (SSE) streaming endpoint for conversational completion with automatic RAG grounding and JIT indexing.
- `GET /api/model` — Returns loaded model metadata (architecture, parameters, quantization, runtime).
- `GET /api/health` — Reports Ollama connection status, loaded models, and service readiness.

### Document & File Management
- `POST /api/files/upload` — Upload an attachment (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`) with path-traversal and MIME validation.
- `GET /api/files/config` — Returns upload size limits and allowed file formats.
- `POST /api/files/{id}/process` — Parse an uploaded attachment and return structured sections.
- `POST /api/files/{id}/chunks` — Generate boundary-aware retrieval chunks with provenance.
- `POST /api/files/{id}/embeddings` — Generate 768-dim dense embeddings for document chunks.
- `POST /api/files/{id}/index` — Atomically index or re-index an attachment into the local SQLite vector store.
- `DELETE /api/files/{id}/index` — Remove an attachment and its vectors from the local vector store.

### Semantic Search
- `POST /api/search` — Perform cosine similarity vector search over stored document chunks with optional multi-attachment scoping and minimum similarity score thresholding.

---

## Testing & Evaluation

### Run Test Suites
```bash
cd backend

# 1. Evaluation Framework Unit Tests (10 sections)
python -m app.evaluation.test_evaluation_suite

# 2. Upload -> JIT Indexing -> Chat Lifecycle Tests (7 scenarios)
python -m app.evaluation.test_lifecycle
```

### Run Evaluation Benchmark
```bash
cd backend
python -m app.evaluation.runner --output grounded.json
```
Benchmark reports are written to `evaluation/results/` at the repository root.

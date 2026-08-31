# Chatbot — Local AI Assistant Foundation

A local-first, privacy-focused AI assistant built with **React + TypeScript + Vite** on the frontend, **FastAPI + Pydantic v2 + HTTPX** on the backend, and **Ollama** serving **Gemma 4 E4B**.

---

## Project Structure

```
Chatbot/
├── frontend/                  # React + TypeScript + Vite + Tailwind CSS v4
│   ├── src/
│   │   ├── components/        # UI components (sidebar, workspace, composer)
│   │   ├── data/              # Seed data & prompt starters
│   │   ├── hooks/             # Custom hooks (useChat state & stream batching)
│   │   ├── layouts/           # AppShell layout
│   │   ├── lib/               # Utility functions (cn class merger)
│   │   ├── services/          # Backend API & SSE stream service
│   │   ├── types/             # TypeScript type definitions
│   │   ├── App.tsx            # Main application component
│   │   ├── main.tsx           # Application entry point
│   │   └── index.css          # Design system tokens & Tailwind imports
│   ├── index.html             # HTML entry point
│   ├── package.json           # Frontend dependencies and scripts
│   ├── tsconfig.json          # Root TypeScript configuration
│   ├── tsconfig.app.json      # App TypeScript configuration
│   ├── tsconfig.node.json     # Node / Vite TypeScript configuration
│   └── vite.config.ts         # Vite bundler & /api proxy configuration
│
├── backend/                   # FastAPI Python backend
│   ├── app/
│   │   ├── models/            # Pydantic v2 request & response schemas
│   │   ├── routes/            # API route endpoints (/api/chat, /api/model, /api/health)
│   │   ├── services/          # Ollama NDJSON to SSE stream adapter
│   │   ├── config.py          # Centralized Pydantic v2 SettingsConfigDict
│   │   └── main.py            # FastAPI entry point & CORS configuration
│   ├── requirements.txt       # Python dependencies
│   └── venv/                  # Python virtual environment
│
├── .env.example               # Example environment configuration
├── .gitignore                 # Repository exclusion rules
└── README.md                  # Project documentation
```

---

## Prerequisites

1. **Ollama**: Ensure [Ollama](https://ollama.com) is installed and running with `gemma4:e4b`:
   ```bash
   ollama pull gemma4:e4b
   ollama serve
   ```
2. **Node.js**: Node 18+ (Node 20+ recommended)
3. **Python**: Python 3.10+

---

## Getting Started

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend server runs on `http://127.0.0.1:8000`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend development server runs on `http://localhost:5173`. Requests to `/api/*` are automatically proxied to the backend at `http://127.0.0.1:8000`.

---

## Available API Endpoints

- `GET /api/health` — Checks connectivity with Ollama and reports model installed/loaded status.
- `GET /api/model` — Returns sanitized model metadata (architecture, parameters, quantization, runtime).
- `POST /api/chat` — Server-Sent Events (SSE) streaming endpoint for conversational completion with `gemma4:e4b`.
- `GET /docs` — Swagger OpenAPI documentation.

---

## Keyboard Shortcuts

- `Enter`: Send message in composer.
- `Shift + Enter`: Insert a newline in composer.
- `Ctrl + N` / `Cmd + N`: Start a new conversation thread.

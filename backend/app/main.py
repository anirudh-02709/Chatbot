import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chatbot.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        f"Starting Chatbot Backend. Ollama Target: {settings.ollama_base_url}, Model: {settings.model_name}"
    )
    yield
    logger.info("Shutting down Chatbot Backend.")


settings = get_settings()

app = FastAPI(
    title="Chatbot Backend",
    description="Local-first AI Assistant backend for Gemma 4 E4B via Ollama",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Configuration for development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(chat_router)


@app.get("/")
async def root():
    return {
        "service": "Chatbot Backend",
        "model": settings.model_name,
        "docs": "/docs",
    }

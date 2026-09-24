import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ev_backend")

from app.database import init_db

def create_app() -> FastAPI:
    app = FastAPI(
        title="E.V AI Personal Assistant Backend",
        description="High-performance Python LLM backend with PostgreSQL DB, Gemini, Groq, Web Search, and Android Studio API integration.",
        version="1.0.0"
    )

    # Enable CORS for Android Studio local connections (emulator 10.0.2.2 and local Wi-Fi devices)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(chat.router)

    @app.on_event("startup")
    async def startup_event():
        logger.info(f"⚡ E.V Backend initialized! Connected Assistant Name: {settings.ASSISTANT_NAME}")
        logger.info(f"Gemini API Configured: {bool(settings.GEMINI_API_KEY)}")
        logger.info(f"Groq API Configured: {bool(settings.GROQ_API_KEY)}")
        await init_db()

    return app

app = create_app()

import logging
import asyncio
import httpx
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

async def keep_alive_loop():
    """Background task that periodically self-pings the server to prevent Render free instance sleeping."""
    await asyncio.sleep(60) # Wait 1 minute before first ping
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get("https://e-v-backend.onrender.com/health")
                logger.info("⚡ Keep-alive self-ping sent successfully!")
        except Exception as e:
            logger.debug(f"Keep-alive self-ping note: {e}")
        await asyncio.sleep(600) # Ping every 10 minutes

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
        asyncio.create_task(keep_alive_loop())

    return app

app = create_app()

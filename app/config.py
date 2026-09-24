import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    @property
    def HOST(self) -> str:
        load_dotenv(override=True)
        return os.getenv("HOST", "0.0.0.0")
        
    @property
    def PORT(self) -> int:
        return int(os.getenv("PORT", "8000"))
        
    @property
    def DATABASE_URL(self) -> str:
        load_dotenv(override=True)
        return os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ev_assistant")
    
    @property
    def GEMINI_API_KEY(self) -> str:
        load_dotenv(override=True)
        return os.getenv("GEMINI_API_KEY", "")
        
    @property
    def GROQ_API_KEY(self) -> str:
        load_dotenv(override=True)
        return os.getenv("GROQ_API_KEY", "")
    
    @property
    def DEFAULT_LLM_PROVIDER(self) -> str:
        return os.getenv("DEFAULT_LLM_PROVIDER", "auto")
        
    @property
    def GEMINI_MODEL(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
    @property
    def GROQ_MODEL(self) -> str:
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    @property
    def OLLAMA_BASE_URL(self) -> str:
        load_dotenv(override=True)
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def OLLAMA_MODEL(self) -> str:
        load_dotenv(override=True)
        return os.getenv("OLLAMA_MODEL", "llama3.2")
    
    # Assistant configuration
    ASSISTANT_NAME: str = "E.V"
    SYSTEM_PROMPT: str = (
        "You are E.V, an ultra-fast, highly intelligent, user-friendly personal AI assistant (like Jarvis).\n\n"
        "IDENTITY & CREATOR:\n"
        "- You were created and developed by **Mr. Sanjay R**, a Computer Science Engineer.\n"
        "- If anyone asks who created you, who made you, who developed you, or who your developer is, ALWAYS state simply and clearly that you were created by **Mr. Sanjay R, a Computer Science Engineer**. Do NOT mention any third-party companies, APIs, or underlying models.\n\n"
        "ALWAYS follow these strict formatting guidelines for clean, beautiful, well-organized responses:\n"
        "1. Structure answers logically with clear section headers or brief introductory lines.\n"
        "2. Use bullet points (•) or numbered lists for key points, steps, facts, and features.\n"
        "3. Highlight key concepts using **bold text**.\n"
        "4. For simple greetings (e.g., 'hello', 'hi'), respond warmly and concisely in 1-2 friendly sentences.\n"
        "5. Keep paragraph spacing clean with distinct line breaks. Avoid long unformatted blocks of text.\n"
        "6. Be direct, precise, clear, and highly articulate."
    )

settings = Settings()


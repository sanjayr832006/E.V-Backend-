import json
import logging
from typing import List, Optional, Dict, Any
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile
from pydantic import BaseModel, Field

from app.services.assistant_service import assistant_service
from app.services.search_service import SearchService
from app.config import settings

logger = logging.getLogger("ev_backend")

router = APIRouter()

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, ACTIVE_DB_TYPE
from app.services.db_service import DatabaseService

class ChatTurn(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Text message content")

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="User query or voice command for E.V assistant")
    provider: Optional[str] = Field("auto", description="LLM provider: 'auto', 'gemini', 'groq', or 'ollama'")
    enable_search: Optional[bool] = Field(None, description="Force enable or disable live web search")
    session_id: Optional[str] = Field(None, description="Optional session ID for PostgreSQL chat history tracking")
    user_id: Optional[str] = Field("default_user", description="Optional user ID for personalized memories & history")
    chat_history: Optional[List[ChatTurn]] = Field(None, description="Previous conversation messages for context")

class SearchSource(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None

class ChatMessageResponse(BaseModel):
    assistant_name: str
    response: str
    provider: str
    model: str
    searched_web: bool
    search_sources: List[SearchSource]
    session_id: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class MemoryRequest(BaseModel):
    user_id: str = Field("default_user")
    key: str
    value: str
    category: Optional[str] = "general"

@router.get("/health")
async def health_check():
    """
    Health check endpoint for Android client connection verification.
    """
    import httpx
    has_gemini = bool(settings.GEMINI_API_KEY)
    has_groq = bool(settings.GROQ_API_KEY)
    has_ollama = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            has_ollama = resp.status_code == 200
    except Exception:
        has_ollama = False
    
    return {
        "status": "online",
        "assistant": settings.ASSISTANT_NAME,
        "database": {
            "type": ACTIVE_DB_TYPE,
            "connected": True
        },
        "providers_configured": {
            "gemini": has_gemini,
            "groq": has_groq,
            "ollama": has_ollama
        },
        "ready": has_gemini or has_groq or has_ollama
    }

@router.post("/api/voice/transcribe")
async def transcribe_audio_endpoint(file: UploadFile = File(...)):
    """
    Transcribes voice recordings using Groq Whisper-large-v3 model (<200ms ultra-fast latency).
    """
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY required for Whisper voice transcription.")

    try:
        content = await file.read()
        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
        files = {"file": (file.filename or "audio.wav", content, file.content_type or "audio/wav")}
        data = {"model": "whisper-large-v3"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=headers, files=files, data=data)
            if resp.status_code == 200:
                transcription = resp.json().get("text", "")
                return {"text": transcription, "status": "success"}
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"Whisper transcription failed: {resp.text}")
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/chat", response_model=ChatMessageResponse)
async def chat_endpoint(request: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
    """
    Main REST endpoint for Android app to talk with E.V assistant.
    Auto-persists message history into database.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        active_session_id = request.session_id or "default_session"
        history_list = None

        # Safely fetch session history from DB if available
        try:
            session_obj = await DatabaseService.get_or_create_session(
                db=db,
                session_id=request.session_id,
                user_id=request.user_id or "default_user",
                title=request.message[:30]
            )
            if session_obj:
                active_session_id = session_obj.id

            if request.chat_history:
                history_list = [turn.model_dump() for turn in request.chat_history]
            elif active_session_id:
                db_msgs = await DatabaseService.get_session_messages(db, active_session_id)
                history_list = [{"role": m["role"], "content": m["content"]} for m in db_msgs]
        except Exception as db_err:
            logger.warning(f"DB session lookup note (continuing chat without history): {db_err}")

        # Process user query via AI Assistant Service
        result = await assistant_service.process_user_query(
            message=request.message,
            provider=request.provider or "auto",
            enable_search=request.enable_search,
            chat_history=history_list
        )

        # Safely persist chat messages to DB
        try:
            await DatabaseService.save_chat_message(
                db=db,
                session_id=active_session_id,
                role="user",
                content=request.message
            )
            await DatabaseService.save_chat_message(
                db=db,
                session_id=active_session_id,
                role="assistant",
                content=result["response"],
                provider=result["provider"],
                model=result["model"],
                searched_web=result["searched_web"],
                search_sources=result["search_sources"]
            )
        except Exception as db_save_err:
            logger.warning(f"DB save message note: {db_save_err}")

        result["session_id"] = active_session_id
        return result
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/sessions")
async def list_sessions_endpoint(user_id: str = "default_user", db: AsyncSession = Depends(get_db)):
    """
    Retrieves all chat sessions for a specific user.
    """
    sessions = await DatabaseService.list_sessions(db, user_id)
    return {"user_id": user_id, "sessions": sessions}

@router.get("/api/sessions/{session_id}/messages")
async def get_session_history_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves full chat message history for a specific session ID from PostgreSQL.
    """
    messages = await DatabaseService.get_session_messages(db, session_id)
    return {"session_id": session_id, "messages": messages}

@router.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Deletes a chat session and all its messages.
    """
    success = await DatabaseService.delete_session(db, session_id)
    return {"session_id": session_id, "deleted": success}

@router.post("/api/memories")
async def save_memory_endpoint(request: MemoryRequest, db: AsyncSession = Depends(get_db)):
    """
    Saves a persistent user memory / preference into PostgreSQL.
    """
    memory = await DatabaseService.save_user_memory(
        db=db,
        user_id=request.user_id,
        key=request.key,
        value=request.value,
        category=request.category or "general"
    )
    return {"saved": True, "memory_id": memory.id, "key": memory.key, "value": memory.value}

@router.get("/api/memories/{user_id}")
async def get_memories_endpoint(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves all persistent memories / saved data for a user.
    """
    memories = await DatabaseService.get_user_memories(db, user_id)
    return {"user_id": user_id, "memories": memories}

@router.post("/api/search")
async def search_endpoint(request: SearchRequest):
    """
    Direct web search endpoint for Android client to query live web search results.
    """
    try:
        results = await SearchService.search_web(request.query, max_results=request.max_results or 5)
        return {"query": request.query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/wikipedia")
async def wikipedia_endpoint(request: SearchRequest):
    """
    Direct Wikipedia lookup endpoint for Android client to query Wikipedia summaries.
    """
    try:
        result = await SearchService.search_wikipedia(request.query)
        if not result:
            return {"query": request.query, "found": False, "result": None}
        return {"query": request.query, "found": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time response streaming to Android client.
    Allows fast Jarvis-like voice interaction with zero delay.
    """
    await websocket.accept()
    logger.info("Android WebSocket client connected.")
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
                message = payload.get("message", "")
                provider = payload.get("provider", "auto")
                enable_search = payload.get("enable_search", None)
            except Exception:
                message = raw_data
                provider = "auto"
                enable_search = None

            if not message:
                await websocket.send_text(json.dumps({"type": "error", "content": "Empty prompt received"}))
                continue

            # Stream response chunks back to Android
            await websocket.send_text(json.dumps({"type": "start", "assistant": settings.ASSISTANT_NAME}))
            async for chunk in assistant_service.stream_user_query(message, provider, enable_search):
                await websocket.send_text(json.dumps({"type": "chunk", "content": chunk}))
            await websocket.send_text(json.dumps({"type": "end"}))

    except WebSocketDisconnect:
        logger.info("Android WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

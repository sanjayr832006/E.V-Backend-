import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from app.models.db_models import ChatSession, ChatMessage, UserMemory, SavedSource

logger = logging.getLogger("ev_backend")

class DatabaseService:
    """
    Database CRUD Operations Service for persistent chat history, sessions, and memories.
    """

    @staticmethod
    async def get_or_create_session(
        db: AsyncSession,
        session_id: Optional[str] = None,
        user_id: str = "default_user",
        title: Optional[str] = None
    ) -> ChatSession:
        if session_id:
            stmt = select(ChatSession).where(ChatSession.id == session_id)
            res = await db.execute(stmt)
            session_obj = res.scalar_one_or_none()
            if session_obj:
                return session_obj

        # Create new session if not found or session_id not given
        new_session = ChatSession(
            id=session_id if session_id else undefined_uuid(),
            user_id=user_id,
            title=title or "New Conversation"
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    @staticmethod
    async def list_sessions(db: AsyncSession, user_id: str = "default_user") -> List[Dict[str, Any]]:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        return [
            {
                "session_id": s.id,
                "user_id": s.user_id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        stmt = delete(ChatSession).where(ChatSession.id == session_id)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0

    @staticmethod
    async def save_chat_message(
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        searched_web: bool = False,
        search_sources: Optional[List[Dict[str, str]]] = None
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            searched_web=searched_web,
            search_sources=search_sources
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    @staticmethod
    async def get_session_messages(db: AsyncSession, session_id: str) -> List[Dict[str, Any]]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
        res = await db.execute(stmt)
        messages = res.scalars().all()
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "provider": m.provider,
                "model": m.model,
                "searched_web": m.searched_web,
                "search_sources": m.search_sources,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]

    @staticmethod
    async def save_user_memory(
        db: AsyncSession,
        user_id: str,
        key: str,
        value: str,
        category: str = "general"
    ) -> UserMemory:
        # Check existing memory with key
        stmt = select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.key == key)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.category = category
            await db.commit()
            await db.refresh(existing)
            return existing

        memory = UserMemory(user_id=user_id, key=key, value=value, category=category)
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def get_user_memories(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id).order_by(UserMemory.created_at.desc())
        res = await db.execute(stmt)
        memories = res.scalars().all()
        return [
            {
                "id": mem.id,
                "user_id": mem.user_id,
                "key": mem.key,
                "value": mem.value,
                "category": mem.category,
                "created_at": mem.created_at.isoformat() if mem.created_at else None
            }
            for mem in memories
        ]

def undefined_uuid() -> str:
    import uuid
    return str(uuid.uuid4())

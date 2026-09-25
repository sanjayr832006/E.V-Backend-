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
        db: Optional[AsyncSession],
        session_id: Optional[str] = None,
        user_id: str = "default_user",
        title: Optional[str] = None
    ) -> Optional[ChatSession]:
        if not db:
            return None

        try:
            if session_id:
                stmt = select(ChatSession).where(ChatSession.id == session_id)
                res = await db.execute(stmt)
                session_obj = res.scalar_one_or_none()
                if session_obj:
                    return session_obj

            new_session = ChatSession(
                id=session_id if session_id else undefined_uuid(),
                user_id=user_id,
                title=title or "New Conversation"
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            return new_session
        except Exception as e:
            logger.warning(f"get_or_create_session db note: {e}")
            return None

    @staticmethod
    async def list_sessions(db: Optional[AsyncSession], user_id: str = "default_user") -> List[Dict[str, Any]]:
        if not db:
            return []
        try:
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
        except Exception as e:
            logger.warning(f"list_sessions db note: {e}")
            return []

    @staticmethod
    async def delete_session(db: Optional[AsyncSession], session_id: str) -> bool:
        if not db:
            return False
        try:
            stmt = delete(ChatSession).where(ChatSession.id == session_id)
            res = await db.execute(stmt)
            await db.commit()
            return res.rowcount > 0
        except Exception as e:
            logger.warning(f"delete_session db note: {e}")
            return False

    @staticmethod
    async def save_chat_message(
        db: Optional[AsyncSession],
        session_id: str,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        searched_web: bool = False,
        search_sources: Optional[List[Dict[str, str]]] = None
    ) -> Optional[ChatMessage]:
        if not db:
            return None
        try:
            serialized_sources = search_sources
            if isinstance(search_sources, list):
                serialized_sources = [
                    {"title": str(s.get("title", "")), "url": str(s.get("url", ""))}
                    for s in search_sources if isinstance(s, dict)
                ]

            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                provider=provider,
                model=model,
                searched_web=searched_web,
                search_sources=serialized_sources
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)
            return message
        except Exception as e:
            logger.warning(f"save_chat_message db note: {e}")
            return None

    @staticmethod
    async def get_session_messages(db: Optional[AsyncSession], session_id: str) -> List[Dict[str, Any]]:
        if not db:
            return []
        try:
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
        except Exception as e:
            logger.warning(f"get_session_messages db note: {e}")
            return []

    @staticmethod
    async def save_user_memory(
        db: Optional[AsyncSession],
        user_id: str,
        key: str,
        value: str,
        category: str = "general"
    ) -> Optional[UserMemory]:
        if not db:
            return None
        try:
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
        except Exception as e:
            logger.warning(f"save_user_memory db note: {e}")
            return None

    @staticmethod
    async def get_user_memories(db: Optional[AsyncSession], user_id: str) -> List[Dict[str, Any]]:
        if not db:
            return []
        try:
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
        except Exception as e:
            logger.warning(f"get_user_memories db note: {e}")
            return []

def undefined_uuid() -> str:
    import uuid
    return str(uuid.uuid4())

import asyncio
import logging
import re
from typing import Dict, Any, AsyncGenerator, List, Optional
from app.config import settings
from app.services.search_service import SearchService
from app.services.llm_service import llm_service

logger = logging.getLogger("ev_backend")

class AssistantService:
    """
    E.V Personal Assistant Core Service.
    Handles user queries, web search trigger evaluation, prompt construction, and response synthesis.
    """

    SEARCH_KEYWORDS = [
        "search", "find", "latest news", "weather", "today's", "current price",
        "stock price", "live score", "recent news", "what happened today", "wikipedia search"
    ]

    def should_search_web(self, query: str) -> bool:
        """
        Determines whether the query likely requires live internet search data.
        """
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.SEARCH_KEYWORDS)

    async def process_user_query(
        self,
        message: str,
        provider: str = "auto",
        enable_search: Optional[bool] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        image_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a user query and returns a structured response.
        """
        perform_search = enable_search if enable_search is not None else self.should_search_web(message)
        search_results = []
        search_context = ""

        # Skip web search if doing image vision task to optimize speed
        if image_base64:
            perform_search = False

        # Check for explicit URLs in the user's message
        urls_in_message = re.findall(r'https?://[^\s]+', message)
        if urls_in_message and not image_base64:
            logger.info(f"Target URL(s) detected in query: {urls_in_message}")
            for target_url in urls_in_message[:2]:
                page_res = await SearchService.fetch_url_content(target_url)
                if page_res:
                    search_results.append(page_res)

        if perform_search and not urls_in_message:
            logger.info(f"Executing parallel web & Wikipedia search for query: '{message}'")
            # Run Wikipedia and Web Search concurrently in parallel!
            wiki_task = SearchService.search_wikipedia(message)
            web_task = SearchService.search_web(message, max_results=3)

            wiki_res, web_res = await asyncio.gather(wiki_task, web_task, return_exceptions=True)

            if isinstance(wiki_res, dict) and wiki_res:
                search_results.append(wiki_res)
            if isinstance(web_res, list) and web_res:
                search_results.extend(web_res)

        if search_results:
            search_context = SearchService.format_search_context(search_results)

        # Build full prompt
        full_prompt = message
        if search_context:
            full_prompt = f"{search_context}\n\nUser Question: {message}\n\nPlease answer the user using the live search context above when relevant."

        # Include chat history if provided
        if chat_history and not image_base64:
            history_str = "=== PREVIOUS CONVERSATION HISTORY ===\n"
            for turn in chat_history[-6:]:  # Last 3 rounds
                role = turn.get("role", "user")
                content = turn.get("content", "")
                history_str += f"{role.upper()}: {content}\n"
            history_str += "=== END HISTORY ===\n\n"
            full_prompt = history_str + full_prompt

        # Execute LLM Generation
        response_data = await llm_service.generate_response(
            prompt=full_prompt,
            system_instruction=settings.SYSTEM_PROMPT,
            provider=provider,
            image_base64=image_base64
        )

        return {
            "assistant_name": settings.ASSISTANT_NAME,
            "response": response_data["text"],
            "provider": response_data["provider"],
            "model": response_data["model"],
            "searched_web": bool(search_results),
            "search_sources": [
                {"title": r.get("title", ""), "url": r.get("href", "")}
                for r in search_results
                if r and isinstance(r, dict)
            ]
        }

    async def stream_user_query(
        self,
        message: str,
        provider: str = "auto",
        enable_search: Optional[bool] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streams response text token by token for real-time speech/voice on Android.
        """
        perform_search = enable_search if enable_search is not None else self.should_search_web(message)
        search_results = []
        search_context = ""

        urls_in_message = re.findall(r'https?://[^\s]+', message)
        if urls_in_message:
            for target_url in urls_in_message[:2]:
                page_res = await SearchService.fetch_url_content(target_url)
                search_results.append(page_res)
        elif perform_search:
            wiki_res = await SearchService.search_wikipedia(message)
            if wiki_res:
                search_results.append(wiki_res)
            web_res = await SearchService.search_web(message, max_results=3)
            search_results.extend(web_res)

        if search_results:
            search_context = SearchService.format_search_context(search_results)

        full_prompt = message
        if search_context:
            full_prompt = f"{search_context}\n\nUser Question: {message}\n\nAnswer using the live context."

        async for chunk in llm_service.generate_stream(
            prompt=full_prompt,
            system_instruction=settings.SYSTEM_PROMPT,
            provider=provider
        ):
            yield chunk

assistant_service = AssistantService()

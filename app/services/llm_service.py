import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("ev_backend")

class LLMService:
    """
    Unified LLM provider service for Google Gemini, Groq, and local Ollama APIs with auto-fallback.
    """

    @property
    def gemini_key(self) -> str:
        return settings.GEMINI_API_KEY

    @property
    def groq_key(self) -> str:
        return settings.GROQ_API_KEY

    @property
    def gemini_model(self) -> str:
        return settings.GEMINI_MODEL

    @property
    def groq_model(self) -> str:
        return settings.GROQ_MODEL

    @property
    def ollama_base_url(self) -> str:
        return settings.OLLAMA_BASE_URL.rstrip('/')

    @property
    def ollama_model(self) -> str:
        return settings.OLLAMA_MODEL

    def get_groq_client(self):
        if self.groq_key:
            try:
                from groq import Groq
                return Groq(api_key=self.groq_key)
            except Exception as e:
                logger.warning(f"Groq SDK initialization note: {e}")
        return None

    def dispatch_model(self, prompt: str) -> tuple[str, str]:
        """
        Smart Model Dispatcher.
        Selects optimal LLM provider & model based on query intent & complexity.
        Returns tuple: (provider_name, model_name)
        """
        prompt_lower = prompt.lower()

        # Heavy coding / reasoning / complex math keywords
        heavy_keywords = ["code", "python", "kotlin", "java", "sql", "function", "algorithm", "debug", "refactor", "math", "equation", "solve", "architecture"]
        is_heavy = any(kw in prompt_lower for kw in heavy_keywords) or len(prompt) > 400

        if is_heavy:
            if self.groq_key:
                return ("groq", "openai/gpt-oss-120b")
            elif self.gemini_key:
                return ("gemini", self.gemini_model)

        # Default fast chat dispatch (Ultra-fast 20B model)
        if self.groq_key:
            return ("groq", "openai/gpt-oss-20b")
        elif self.gemini_key:
            return ("gemini", self.gemini_model)

        return ("ollama", self.ollama_model)

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        provider: str = "auto"
    ) -> Dict[str, Any]:
        """
        Generates complete text response with provider routing and fallback.
        """
        try:
            chosen_provider = provider.lower()
            target_model = self.groq_model

            if chosen_provider == "auto":
                chosen_provider, target_model = self.dispatch_model(prompt)

            if chosen_provider == "groq" and self.groq_key:
                try:
                    res = await self._call_groq(prompt, system_instruction, model_override=target_model)
                    return {"text": res, "provider": "groq", "model": target_model}
                except Exception as e:
                    logger.warning(f"Groq primary note: {e}")

            if self.gemini_key:
                try:
                    res = await self._call_gemini(prompt, system_instruction)
                    return {"text": res, "provider": "gemini", "model": self.gemini_model}
                except Exception as e:
                    logger.warning(f"Gemini fallback note: {e}")

            if self.groq_key:
                try:
                    res = await self._call_groq(prompt, system_instruction, model_override="openai/gpt-oss-20b")
                    return {"text": res, "provider": "groq", "model": "openai/gpt-oss-20b"}
                except Exception as e:
                    logger.warning(f"Groq secondary fallback note: {e}")

            return {
                "text": "Hello! I am E.V, your personal AI assistant. How can I assist you today?",
                "provider": "E.V Assistant",
                "model": "v1.0"
            }
        except Exception as ex:
            logger.error(f"Global LLM exception: {ex}")
            return {
                "text": "Hello! I am E.V, your personal AI assistant. How can I assist you today?",
                "provider": "E.V Assistant",
                "model": "v1.0"
            }
        else:
            if self.groq_key:
                try:
                    res = await self._call_groq(prompt, system_instruction)
                    return {"text": res, "provider": "groq", "model": self.groq_model}
                except Exception:
                    pass
            if self.gemini_key:
                try:
                    res = await self._call_gemini(prompt, system_instruction)
                    return {"text": res, "provider": "gemini", "model": self.gemini_model}
                except Exception:
                    pass
            # Try local Ollama if available
            try:
                res = await self._call_ollama(prompt, system_instruction)
                return {"text": res, "provider": "ollama", "model": self.ollama_model}
            except Exception:
                pass

            return {
                "text": (
                    "Hello! I am E.V, your personal AI assistant. "
                    "Please configure your GEMINI_API_KEY, GROQ_API_KEY, or run local Ollama to enable AI intelligence!"
                ),
                "provider": "none",
                "model": "offline"
            }

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        provider: str = "auto"
    ) -> AsyncGenerator[str, None]:
        """
        Streams response chunks in real-time for voice & fast Android response.
        """
        chosen_provider = provider.lower()

        if chosen_provider == "ollama":
            try:
                async for chunk in self._stream_ollama(prompt, system_instruction):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Ollama streaming error: {e}")
                raise e

        if chosen_provider == "auto":
            chosen_provider = "groq" if self.groq_key else ("gemini" if self.gemini_key else "ollama")

        if chosen_provider == "groq" and self.groq_key:
            try:
                async for chunk in self._stream_groq(prompt, system_instruction):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Groq streaming error: {e}")

        if self.gemini_key:
            try:
                async for chunk in self._stream_gemini(prompt, system_instruction):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"Gemini streaming error: {e}")

        # Try local Ollama as streaming fallback
        try:
            async for chunk in self._stream_ollama(prompt, system_instruction):
                yield chunk
            return
        except Exception as e:
            logger.error(f"Ollama stream fallback error: {e}")

        # Fallback message
        full_res = await self.generate_response(prompt, system_instruction, provider)
        yield full_res["text"]

    async def _call_groq(self, prompt: str, system_instruction: Optional[str] = None, model_override: Optional[str] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        active_model = model_override or self.groq_model
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": active_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _stream_groq(self, prompt: str, system_instruction: Optional[str] = None) -> AsyncGenerator[str, None]:
        res = await self._call_groq(prompt, system_instruction)
        words = res.split(" ")
        for i in range(0, len(words), 3):
            yield " ".join(words[i:i+3]) + " "
            await asyncio.sleep(0.01)

    async def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        # Direct HTTP API call for Gemini to ensure 100% reliability regardless of SDK version installed
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
        
        contents = [{"parts": [{"text": prompt}]}]
        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                # Fallback to gemini-1.5-flash if 2.5-flash endpoint is restricted
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                resp = await client.post(fallback_url, json=payload)
            
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text_result = "".join([p.get("text", "") for p in parts])
                return text_result
            return ""

    async def _stream_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> AsyncGenerator[str, None]:
        # For simplicity and reliability, fetch full response and yield in responsive chunks
        text = await self._call_gemini(prompt, system_instruction)
        words = text.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            yield " ".join(words[i:i+chunk_size]) + " "
            await asyncio.sleep(0.02)

    async def _call_ollama(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Calls local Ollama instance for LLM generation.
        """
        url = f"{self.ollama_base_url}/api/chat"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    async def _stream_ollama(self, prompt: str, system_instruction: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Streams response chunks from local Ollama instance in real-time.
        """
        import json
        url = f"{self.ollama_base_url}/api/chat"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk_json = json.loads(line)
                            chunk_content = chunk_json.get("message", {}).get("content", "")
                            if chunk_content:
                                yield chunk_content
                        except json.JSONDecodeError:
                            continue

llm_service = LLMService()


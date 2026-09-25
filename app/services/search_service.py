import asyncio
import logging
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("ev_backend")

class SearchService:
    """
    Real-time Internet Information Retrieval Service for E.V assistant.
    Fetches snippets and current web context using DuckDuckGo or web scraping.
    """

    @staticmethod
    async def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Executes a real-time web search for the given query.
        Returns a list of dicts with 'title', 'href', and 'body'.
        """
        results = []
        # Attempt 1: DuckDuckGo Search package
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                ddg_gen = ddgs.text(query, max_results=max_results)
                for item in ddg_gen:
                    results.append({
                        "title": item.get("title", ""),
                        "href": item.get("href", ""),
                        "body": item.get("body", "")
                    })
            if results:
                return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search package fallback triggered: {e}")

        # Attempt 2: Direct HTTP Search fallback
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(f"https://html.duckduckgo.com/html/?q={httpx.URL(query).raw_path}")
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_="result__snippet", limit=max_results):
                        parent = a.find_parent("div", class_="result__body")
                        title_tag = parent.find("a", class_="result__a") if parent else None
                        results.append({
                            "title": title_tag.get_text(strip=True) if title_tag else "Web Result",
                            "href": title_tag["href"] if title_tag and "href" in title_tag.attrs else "",
                            "body": a.get_text(strip=True)
                        })
        except Exception as ex:
            logger.error(f"HTTP web search failed: {ex}")

        return results

    @staticmethod
    async def fetch_url_content(url: str) -> Dict[str, str]:
        """
        Scrapes readable text content directly from a specified website URL.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for elem in soup(["script", "style", "nav", "footer", "header"]):
                        elem.decompose()
                    text = soup.get_text(separator=" ", strip=True)
                    title = soup.title.string if soup.title else url
                    return {"title": str(title), "href": url, "body": text[:4000]}
        except Exception as e:
            logger.error(f"Failed to fetch content from URL {url}: {e}")
            return {"title": url, "href": url, "body": ""}

    @staticmethod
    async def search_wikipedia(query: str) -> Optional[Dict[str, str]]:
        """
        Fetches an encyclopedic summary directly from Wikipedia REST API for the query.
        """
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            headers = {"User-Agent": "EVAssistant/1.0 (contact@evassistant.ai)"}
            async with httpx.AsyncClient(headers=headers, timeout=8.0, follow_redirects=True) as client:
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&format=json"
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    search_hits = resp.json().get("query", {}).get("search", [])
                    if search_hits:
                        top_title = search_hits[0].get("title", "")
                        encoded_title = urllib.parse.quote(top_title)
                        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
                        sum_resp = await client.get(summary_url)
                        if sum_resp.status_code == 200:
                            sum_data = sum_resp.json()
                            extract = sum_data.get("extract", "")
                            page_url = sum_data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{encoded_title}")
                            if extract:
                                return {
                                    "title": f"Wikipedia: {top_title}",
                                    "href": page_url,
                                    "body": extract
                                }
        except Exception as e:
            logger.warning(f"Wikipedia API lookup exception for '{query}': {e}")
        return None

    @staticmethod
    def format_search_context(search_results: List[Dict[str, str]]) -> str:
        """
        Formats search results into a clean context block for the LLM.
        """
        if not search_results:
            return ""

        context_str = "=== REAL-TIME INTERNET SEARCH RESULTS ===\n"
        for i, res in enumerate(search_results, 1):
            if not res or not isinstance(res, dict):
                continue
            context_str += f"Source [{i}]: {res.get('title', '')}\n"
            if res.get('href'):
                context_str += f"URL: {res.get('href')}\n"
            context_str += f"Content: {res.get('body', '')}\n\n"
        context_str += "=== END SEARCH RESULTS ===\n"
        return context_str

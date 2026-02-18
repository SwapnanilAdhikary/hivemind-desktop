"""Built-in tools for web-related operations."""

import json
import re
from urllib.request import urlopen, Request
from urllib.parse import quote_plus


def web_search_snippet(query: str) -> str:
    """Search the web and return a text snippet (uses DuckDuckGo instant answers)."""
    try:
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
        req = Request(url, headers={"User-Agent": "AgentPlatform/0.1"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            abstract = data.get("AbstractText", "")
            if abstract:
                return abstract
            related = data.get("RelatedTopics", [])
            if related and isinstance(related[0], dict):
                return related[0].get("Text", "No results found")
            return "No results found"
    except Exception as e:
        return f"Search failed: {e}"


def fetch_url_text(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and return the text content (HTML tags stripped)."""
    try:
        req = Request(url, headers={"User-Agent": "AgentPlatform/0.1"})
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
    except Exception as e:
        return f"Fetch failed: {e}"

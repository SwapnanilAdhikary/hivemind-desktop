"""Built-in tools for text processing."""

import re
import json
from datetime import datetime


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Extract the first N sentences as a rough summary."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:max_sentences])


def extract_emails(text: str) -> list:
    """Extract all email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(pattern, text)


def extract_urls(text: str) -> list:
    """Extract all URLs from text."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(pattern, text)


def word_count(text: str) -> dict:
    """Count words, characters, and sentences in text."""
    words = text.split()
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return {
        "words": len(words),
        "characters": len(text),
        "sentences": len(sentences),
    }


def get_current_datetime() -> str:
    """Return the current date and time in ISO format."""
    return datetime.now().isoformat()

import re
from datetime import date, datetime
from typing import Optional, List


# Common stop words for keyword extraction
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "this", "that", "these",
    "those", "it", "its", "we", "our", "you", "your", "they", "their",
    "all", "any", "each", "more", "also", "other", "such", "than", "as",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "while",
    "if", "unless", "although", "because", "since", "until", "when",
}

# Grant-specific domain keywords to boost
_DOMAIN_KEYWORDS = {
    "research", "funding", "grant", "award", "scholarship", "fellowship",
    "project", "program", "initiative", "innovation", "development",
    "health", "medical", "science", "technology", "education", "community",
    "environment", "energy", "agriculture", "defense", "arts", "humanities",
}


def clean_html(text: Optional[str]) -> Optional[str]:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return None
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&nbsp;": " ", "&quot;": '"', "&#39;": "'",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def clean_title(title: Optional[str]) -> Optional[str]:
    """Clean and normalize a grant title."""
    if not title:
        return None
    title = clean_html(title)
    # Remove leading/trailing punctuation
    title = title.strip(".,;:-")
    # Truncate to 500 chars
    return title[:500].strip() if title else None


def extract_keywords(text: Optional[str], max_keywords: int = 15) -> List[str]:
    """Extract meaningful keywords from text using frequency + domain boosting."""
    if not text:
        return []

    # Tokenize: lowercase, letters only
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())

    # Filter stop words, count frequencies
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP_WORDS:
            # Domain keywords get boosted weight
            boost = 3 if w in _DOMAIN_KEYWORDS else 1
            freq[w] = freq.get(w, 0) + boost

    # Sort by frequency, return top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]


def parse_date(value: Optional[str | date]) -> Optional[date]:
    """Parse a date from various string formats."""
    if value is None:
        return None
    if isinstance(value, date):
        return value

    formats = [
        "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value) -> Optional[float]:
    """Parse a monetary amount from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        result = float(cleaned)
        return result if result > 0 else None
    except ValueError:
        return None


def normalize_status(status: Optional[str]) -> str:
    """Normalize grant status to a known set of values."""
    if not status:
        return "unknown"
    status_lower = status.lower().strip()
    mapping = {
        "posted": "open",
        "open": "open",
        "active": "open",
        "forecasted": "forecasted",
        "forecast": "forecasted",
        "closed": "closed",
        "archived": "closed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    for key, val in mapping.items():
        if key in status_lower:
            return val
    return "unknown"

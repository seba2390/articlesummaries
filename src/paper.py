from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Paper:
    """Represents a single academic paper.

    This data class standardizes the information extracted from various sources
    (like arXiv) and used throughout the application (filtering, output, etc.).
    """

    id: str  # Unique identifier (e.g., arXiv ID with version)
    title: str  # Title of the paper
    authors: List[str] = field(default_factory=list)  # List of author names
    abstract: str = ""  # Paper abstract or summary
    url: str = ""  # URL to the paper (e.g., arXiv abstract page URL)
    published_date: Optional[datetime] = None  # Publication or last update date (timezone-aware if possible)
    source: str = "unknown"  # Source identifier (e.g., 'arxiv')
    categories: List[str] = field(default_factory=list)  # Subject categories (e.g., ['cs.AI', 'cs.LG'])

    # Fields added during processing:
    relevance: Optional[Dict[str, Any]] = field(
        default=None
    )  # Relevance info from LLM check (e.g., {'confidence': 0.9, 'explanation': '...'})
    matched_keywords: Optional[List[str]] = field(default=None)  # Keywords from config that matched this paper

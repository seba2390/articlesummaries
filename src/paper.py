from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Paper:
    """A simple data class to represent a paper."""

    id: str
    title: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    published_date: datetime | None = None
    source: str = "unknown"  # To track where the paper came from (e.g., 'arxiv')

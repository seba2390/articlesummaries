from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.paper import Paper


class BaseFilter(ABC):
    """Abstract base class for paper filtering strategies."""

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configure the filter with necessary parameters."""
        pass

    @abstractmethod
    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filter a list of papers based on specific criteria."""
        pass

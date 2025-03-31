from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.paper import Paper


class BasePaperSource(ABC):
    """Abstract base class for paper sources like arXiv."""

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configure the source with necessary parameters."""
        pass

    @abstractmethod
    def fetch_papers(self) -> List[Paper]:
        """Fetch recent papers from the source."""
        pass

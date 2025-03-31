from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.paper import Paper


class BaseOutput(ABC):
    """Abstract base class for handling the output of relevant papers."""

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configure the output handler with necessary parameters."""
        pass

    @abstractmethod
    def output(self, papers: List[Paper]):
        """Process and output the list of relevant papers."""
        pass

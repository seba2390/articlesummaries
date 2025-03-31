"""Defines the abstract base class for all paper filtering strategies."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Assuming src.paper.Paper is always available in the project structure
from src.paper import Paper


class BaseFilter(ABC):
    """Abstract Base Class for different paper filtering strategies.

    Defines the interface for classes that implement specific ways to filter
    a list of papers based on certain criteria (e.g., keywords, topic models).
    """

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the filter instance.

        Extracts necessary parameters (e.g., keywords, model paths) from the
        provided configuration dictionary specific to this filter's needs.

        Args:
            config: A dictionary containing configuration parameters relevant
                    to this specific filter.
        """
        pass

    @abstractmethod
    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters a list of papers based on the implemented strategy.

        Args:
            papers: A list of `Paper` objects to be filtered.

        Returns:
            A new list containing only the `Paper` objects that match the
            filter's criteria.
        """
        pass

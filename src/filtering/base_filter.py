"""Defines the abstract base class for all paper filtering strategies."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Assuming src.paper.Paper is always available in the project structure
from src.paper import Paper


class BaseFilter(ABC):
    """Abstract Base Class (ABC) defining the interface for paper filters.

    All concrete filtering strategies (e.g., KeywordFilter, potentially an
    LLMEmbeddingsFilter in the future) MUST inherit from this class and
    implement its abstract methods (`configure` and `filter`).

    This ensures consistent interaction with different filtering methods within
    the application.
    """

    @abstractmethod
    def __init__(self):
        """Abstract initializer for filter strategies."""
        # Concrete implementations should initialize their specific attributes here.
        # e.g., self.keywords = [] or self.model = None
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the filter instance using settings from the application config.

        Subclasses must implement this method to read their specific configuration
        details (e.g., list of keywords, path to a model file, API keys)
        from the provided dictionary and store them as instance attributes.

        Args:
            config: The main application configuration dictionary. Implementations
                    should access the relevant section(s) for their parameters.
        """
        raise NotImplementedError  # Ensure subclasses implement this

    @abstractmethod
    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Applies the filter logic to a list of papers.

        Subclasses must implement this method to evaluate each paper in the
        input list against the filter's criteria (based on its configuration)
        and return a new list containing only the papers that pass the filter.

        Args:
            papers: The list of `Paper` objects to be filtered.

        Returns:
            A new list containing only the `Paper` objects that satisfy the
            filter's criteria.
        """
        raise NotImplementedError  # Ensure subclasses implement this

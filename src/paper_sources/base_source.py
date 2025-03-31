"""Defines the abstract base class for all paper sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Keep direct import as Paper is essential for this module
from src.paper import Paper


class BasePaperSource(ABC):
    """Abstract Base Class for different paper sources.

    Defines the interface that all concrete paper source implementations
    (like ArxivSource) must adhere to. This allows the main application
    to treat different sources uniformly.
    """

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the paper source instance.

        This method should extract necessary configuration parameters
        (e.g., API keys, categories, fetch limits) from the provided
        configuration dictionary.

        Args:
            config: A dictionary containing configuration parameters relevant
                    to this specific paper source.
        """
        pass

    @abstractmethod
    def fetch_papers(self) -> List[Paper]:
        """Fetches papers from the source based on its configuration.

        This method should implement the logic to interact with the
        specific paper source (e.g., call an API), retrieve papers
        matching the configured criteria, and convert them into a
        standardized list of `Paper` objects.

        Returns:
            A list of `Paper` objects fetched from the source.
            Returns an empty list if no papers are found or an error occurs.
        """
        pass

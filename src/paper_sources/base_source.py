"""Defines the abstract base class for all paper sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Keep direct import as Paper is essential for this module
from src.paper import Paper


class BasePaperSource(ABC):
    """Abstract Base Class (ABC) defining the interface for paper sources.

    All concrete paper source implementations (e.g., ArxivSource, potentially
    HALSource, PubMedSource in the future) MUST inherit from this class and
    implement its abstract methods (`configure` and `fetch_papers`).

    This ensures that the main application logic can interact with different
    sources in a consistent way, promoting modularity and extensibility.
    """

    @abstractmethod
    def __init__(self):
        """Abstract initializer for paper sources."""
        # Concrete implementations should initialize their specific attributes here.
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the paper source instance using settings from the application config.

        Subclasses must implement this method to read their specific configuration
        details (e.g., API endpoints, search categories, result limits, credentials)
        from the provided dictionary and store them as instance attributes.

        Args:
            config: The main application configuration dictionary. Implementations
                    should typically access their specific section, e.g.,
                    `config.get('paper_source', {}).get('arxiv', {})`.
        """
        raise NotImplementedError  # Ensure subclasses implement this

    @abstractmethod
    def fetch_papers(self) -> List[Paper]:
        """Fetches papers from the configured source according to its settings.

        Subclasses must implement this method to perform the core logic of:
        1. Interacting with the external source (e.g., querying an API).
        2. Retrieving paper data based on the configuration set in `configure`.
        3. Converting the retrieved data into a list of standardized `Paper` objects.
        4. Handling potential errors during the fetching process gracefully.

        Returns:
            A list of `Paper` objects fetched from the source. Returns an empty
            list `[]` if no papers are found matching the criteria or if a
            non-critical error occurs during fetching.
        """
        raise NotImplementedError  # Ensure subclasses implement this

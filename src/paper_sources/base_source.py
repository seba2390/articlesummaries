"""Defines the abstract base class for all paper sources."""

from abc import ABC, abstractmethod
from datetime import datetime
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

    DEFAULT_FETCH_WINDOW_DAYS = 1  # Define a default constant

    @abstractmethod
    def __init__(self):
        """Abstract initializer for paper sources."""
        # Concrete implementations should initialize their specific attributes here.
        # Add fetch_window_days with a default value
        self.fetch_window_days: int = self.DEFAULT_FETCH_WINDOW_DAYS
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any], source_name: str):
        """Configures the paper source instance using settings from the application config.

        Subclasses must implement this method to read their specific configuration
        details (e.g., API endpoints, search categories, result limits, credentials)
        from the provided dictionary and store them as instance attributes.

        Args:
            config: The main application configuration dictionary. Implementations
                    should typically access their specific section using the source_name,
                    e.g., `config.get('paper_source', {}).get(source_name, {})`.
            source_name: The identifier of the source (e.g., 'arxiv', 'biorxiv').
        """
        raise NotImplementedError  # Ensure subclasses implement this

    @abstractmethod
    def fetch_papers(self, start_time_utc: datetime, end_time_utc: datetime) -> List[Paper]:
        """Fetches papers from the configured source within a specified time window.

        Subclasses must implement this method to perform the core logic of:
        1. Interacting with the external source (e.g., querying an API).
        2. Retrieving paper data based on the configuration set in `configure`,
           filtered by the provided `start_time_utc` and `end_time_utc`.
        3. Converting the retrieved data into a list of standardized `Paper` objects.
        4. Handling potential errors during the fetching process gracefully.

        Args:
            start_time_utc: The start of the time window (inclusive, UTC).
            end_time_utc: The end of the time window (inclusive, UTC).

        Returns:
            A list of `Paper` objects fetched from the source. Returns an empty
            list `[]` if no papers are found matching the criteria or if a
            non-critical error occurs during fetching.
        """
        raise NotImplementedError  # Ensure subclasses implement this

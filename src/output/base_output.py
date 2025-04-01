"""Defines the abstract base class for all output handlers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Assuming src.paper.Paper is always available
from src.paper import Paper


class BaseOutput(ABC):
    """Abstract Base Class (ABC) defining the interface for output handlers.

    All concrete output handlers (e.g., FileWriter) MUST inherit from this class
    and implement its abstract methods (`configure` and `output`).

    This ensures that the main application logic can use different output
    mechanisms interchangeably based on configuration.
    """

    @abstractmethod
    def __init__(self):
        """Abstract initializer for output handlers."""
        # Concrete implementations should initialize their specific attributes here.
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the output handler instance using settings from the application config.

        Subclasses must implement this method to read their specific configuration
        details (e.g., output file path, formatting options, API keys for webhooks)
        from the provided dictionary and store them as instance attributes.

        Args:
            config: The configuration dictionary specific to this output handler
                    (typically extracted from the main config, e.g., `config['output']`).
        """
        raise NotImplementedError  # Ensure subclasses implement this

    @abstractmethod
    def output(self, papers: List[Paper]):
        """Processes and outputs the list of relevant papers.

        Subclasses must implement this method to perform the actual output action,
        such as writing to a file, printing to console, sending data to an API, etc.
        Implementations should handle the case where the `papers` list is empty.

        Args:
            papers: A list of `Paper` objects deemed relevant.
        """
        raise NotImplementedError  # Ensure subclasses implement this

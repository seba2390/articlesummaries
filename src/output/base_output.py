"""Defines the abstract base class for all output handlers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

# Assuming src.paper.Paper is always available
from src.paper import Paper


class BaseOutput(ABC):
    """Abstract Base Class for handling the output of relevant papers.

    Defines the interface for classes responsible for taking a list of
    relevant papers and processing them (e.g., writing to a file,
    sending an email, posting to a webhook).
    """

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Configures the output handler instance.

        Extracts necessary parameters (e.g., output filename, email credentials)
        from the provided configuration dictionary specific to this handler.

        Args:
            config: A dictionary containing configuration parameters relevant
                    to this specific output handler.
        """
        pass

    @abstractmethod
    def output(self, papers: List[Paper]):
        """Processes and outputs the list of relevant papers.

        Args:
            papers: A list of `Paper` objects deemed relevant by the filters.
                    This list might be empty.
        """
        pass

"""Base abstract class for LLM-based relevance checking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class LLMResponse:
    """Standardized response structure for LLM relevance checks.

    Attributes:
        is_relevant: Boolean indicating if the paper is deemed relevant.
        confidence: A score (typically 0.0 to 1.0) indicating the LLM's
                    confidence in its relevance assessment.
        explanation: A textual explanation provided by the LLM for its decision.
    """

    is_relevant: bool = False  # Default to False
    confidence: float = 0.0  # Default confidence
    explanation: str = "No explanation provided."  # Default explanation


class BaseLLMChecker(ABC):
    """Abstract base class defining the interface for LLM relevance checkers.

    Concrete implementations should inherit from this class and implement
    the `check_relevance` and `check_relevance_batch` methods for interacting
    with specific LLM APIs (e.g., Groq, OpenAI, Anthropic).
    """

    @abstractmethod
    def __init__(self, **kwargs):
        """Initialize the checker, potentially with API keys, models, etc."""
        # Concrete implementations should define their specific parameters.
        # Example: def __init__(self, api_key: str, model: str = "default-model"): ...
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the name of the LLM provider (e.g., 'groq', 'openai')."""
        raise NotImplementedError

    @abstractmethod
    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Checks the relevance of a single paper abstract using the LLM.

        Args:
            abstract: The abstract text of the paper.
            prompt: The specific prompt guiding the LLM's relevance assessment.

        Returns:
            An LLMResponse object containing the relevance decision, confidence score,
            and a textual explanation.
        """
        raise NotImplementedError  # Ensure subclasses implement this

    @abstractmethod
    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Checks the relevance of multiple paper abstracts in a batch.

        This method is preferred for efficiency when checking multiple papers,
        as it can potentially leverage batching capabilities of the underlying LLM API.

        Args:
            abstracts: A list of abstract texts for the papers.
            prompt: The prompt guiding the LLM's relevance assessment for all abstracts.

        Returns:
            A list of LLMResponse objects, corresponding to the input abstracts
            in the same order.
        """
        raise NotImplementedError  # Ensure subclasses implement this

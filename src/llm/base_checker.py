"""Base abstract class for LLM-based relevance checking."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class LLMResponse:
    """Response from an LLM relevance checker."""

    is_relevant: bool
    confidence: float
    explanation: str


class BaseLLMChecker(ABC):
    """Abstract base class for LLM-based relevance checking."""

    @abstractmethod
    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Check if a paper is relevant based on its abstract and a prompt.

        Args:
            abstract: The paper's abstract text
            prompt: The prompt to use for relevance checking

        Returns:
            LLMResponse containing relevance decision, confidence, and explanation
        """
        pass

    @abstractmethod
    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Check relevance for multiple abstracts in a single batch.

        Args:
            abstracts: List of paper abstracts to check
            prompt: The prompt to use for relevance checking

        Returns:
            List of LLMResponse objects, one for each abstract
        """
        pass

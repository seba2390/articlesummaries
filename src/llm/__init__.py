"""LLM-based relevance checking module."""

from .base_checker import BaseLLMChecker, LLMResponse
from .groq_checker import GroqChecker

# Define what is available for import using `from src.llm import *`
__all__ = [
    "BaseLLMChecker",  # Abstract base class for checkers
    "LLMResponse",  # Dataclass for LLM responses
    "GroqChecker",  # Concrete implementation using Groq API
]

"""
LLM Provider base class (abstract interface).

All business logic depends on LLMProvider, not on GeminiProvider directly.
Swap in a different provider by subclassing LLMProvider and injecting it.
"""
from abc import ABC, abstractmethod
from app.schema.ast import ASTNode


class LLMProvider(ABC):
    """Abstract LLM provider — the rest of the Autoformalizer depends on this."""

    @abstractmethod
    def extract_ast(self, criterion_text: str) -> ASTNode:
        """
        Send criterion_text to the LLM and return a validated ASTNode.
        Raises LLMError on any failure (API, timeout, parse, etc.).
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class LLMError(Exception):
    """Raised for any LLM-level failure: API, timeout, parse, schema, etc."""
    def __init__(self, message: str, error_code: str = "LLM_API_ERROR"):
        super().__init__(message)
        self.error_code = error_code

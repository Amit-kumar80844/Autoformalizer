"""
Machine-readable error codes for every failure mode in the Autoformalizer.
Every error object includes: code, stage, message, and optionally source_text.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ErrorCode(str, Enum):
    UNKNOWN_VARIABLE              = "UNKNOWN_VARIABLE"
    UNSUPPORTED_CONCEPT           = "UNSUPPORTED_CONCEPT"
    INVALID_LLM_OUTPUT            = "INVALID_LLM_OUTPUT"
    SCHEMA_VALIDATION_ERROR       = "SCHEMA_VALIDATION_ERROR"
    TYPE_MISMATCH                 = "TYPE_MISMATCH"
    MISSING_VALUE                 = "MISSING_VALUE"
    AMBIGUOUS_CRITERION           = "AMBIGUOUS_CRITERION"
    UNSUPPORTED_TEMPORAL          = "UNSUPPORTED_TEMPORAL_EXPRESSION"
    SMT_GENERATION_ERROR          = "SMT_GENERATION_ERROR"
    SMT_PARSE_ERROR               = "SMT_PARSE_ERROR"
    Z3_ERROR                      = "Z3_ERROR"
    LLM_TIMEOUT                   = "LLM_TIMEOUT"
    LLM_API_ERROR                 = "LLM_API_ERROR"
    LLM_RATE_LIMIT                = "LLM_RATE_LIMIT"
    LLM_EMPTY_RESPONSE            = "LLM_EMPTY_RESPONSE"
    NORMALIZATION_ERROR           = "NORMALIZATION_ERROR"
    OPERATOR_NOT_ALLOWED          = "OPERATOR_NOT_ALLOWED"
    INVALID_OPERATOR              = "INVALID_OPERATOR"


class FormalizerError(BaseModel):
    code: ErrorCode
    stage: str          # e.g. "llm_extraction", "semantic_validation", "smt_generation", "z3"
    message: str
    source_text: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.code}] ({self.stage}) {self.message}"

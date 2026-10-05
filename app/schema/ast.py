"""
Full Pydantic AST schema for the Autoformalizer.

Nodes:
  ComparisonNode  – numeric / string comparison  (age >= 18)
  BooleanNode     – boolean predicate            (egfr_positive == true)
  MembershipNode  – set membership               (cancer_type IN ["NSCLC","SCLC"])
  TemporalNode    – temporal relationship         (within 6 months of enrollment)
  UnresolvedNode  – clause that could not be safely formalized
  AndNode / OrNode / NotNode – logical composition

TrialFormalization – the complete pipeline output.
"""

from __future__ import annotations
from typing import List, Optional, Union, Literal, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


# ── Primitives ─────────────────────────────────────────────────────────────────

class Operator(str, Enum):
    EQ  = "=="
    NEQ = "!="
    GT  = ">"
    GTE = ">="
    LT  = "<"
    LTE = "<="
    IN  = "IN"


class TemporalRelation(str, Enum):
    BEFORE    = "BEFORE"
    AFTER     = "AFTER"
    WITHIN    = "WITHIN"
    AT_LEAST  = "AT_LEAST"
    BETWEEN   = "BETWEEN"


# ── Base ───────────────────────────────────────────────────────────────────────

class BaseNode(BaseModel):
    source_text: str = Field(..., description="The original text that produced this node.")
    source_span: Optional[List[int]] = Field(
        None, description="[start, end] character offsets into the original criterion text."
    )


# ── Leaf nodes ─────────────────────────────────────────────────────────────────

class ComparisonNode(BaseNode):
    type: Literal["comparison"] = "comparison"
    variable: str = Field(..., description="Canonical variable name from the ontology.")
    operator: Operator
    value: Union[int, float, str, bool]
    unit: Optional[str] = None


class BooleanNode(BaseNode):
    type: Literal["boolean"] = "boolean"
    variable: str = Field(..., description="Canonical variable name from the ontology.")
    value: bool


class MembershipNode(BaseNode):
    type: Literal["membership"] = "membership"
    variable: str
    values: List[str] = Field(..., description="The set of allowed values.")


class TemporalNode(BaseNode):
    type: Literal["temporal"] = "temporal"
    event: str = Field(..., description="The clinical event (e.g. 'prior_chemotherapy').")
    relation: TemporalRelation
    reference: str = Field(..., description="Reference point (e.g. 'enrollment', 'diagnosis').")
    amount: Optional[int] = None
    unit: Optional[str] = Field(None, description="Time unit: days, months, years.")


class UnresolvedNode(BaseNode):
    type: Literal["unresolved"] = "unresolved"
    reason: str = Field(..., description="Why the clause could not be safely formalized.")


# ── Recursive logical nodes ────────────────────────────────────────────────────
# We need forward-refs because And/Or/Not nest themselves.

_AnyNode = Union[
    ComparisonNode,
    BooleanNode,
    MembershipNode,
    TemporalNode,
    UnresolvedNode,
    "AndNode",
    "OrNode",
    "NotNode",
]


class AndNode(BaseNode):
    type: Literal["and"] = "and"
    conditions: List[_AnyNode]


class OrNode(BaseNode):
    type: Literal["or"] = "or"
    conditions: List[_AnyNode]


class NotNode(BaseNode):
    type: Literal["not"] = "not"
    condition: _AnyNode


# Rebuild so forward-refs resolve
AndNode.model_rebuild()
OrNode.model_rebuild()
NotNode.model_rebuild()


ASTNode = Union[
    ComparisonNode,
    BooleanNode,
    MembershipNode,
    TemporalNode,
    UnresolvedNode,
    AndNode,
    OrNode,
    NotNode,
]


# ── Output schema ──────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    passed: bool
    warnings: List[str] = []
    errors: List[str] = []


class ModelMetadata(BaseModel):
    model: str
    temperature: float
    prompt_version: str
    schema_version: str
    ontology_version: str
    formalizer_version: str
    input_hash: str
    latency_ms: Optional[float] = None


class CriterionResult(BaseModel):
    """One resolved or unresolved criterion, preserving its source text."""
    source_text: str
    criterion_type: Literal["inclusion", "exclusion"]
    status: Literal["resolved", "unresolved"]
    ast: Optional[ASTNode] = None
    reason: Optional[str] = None  # only when unresolved


class TrialFormalization(BaseModel):
    trial_id: str
    status: Literal["SUCCESS", "PARTIAL", "FAILED"]
    formal_ast: Optional[ASTNode] = None
    smt_lib: Optional[str] = None
    required_variables: List[str] = []
    criteria: List[CriterionResult] = []
    unresolved_items: List[UnresolvedNode] = []
    warnings: List[str] = []
    errors: List[str] = []
    validation: Optional[ValidationResult] = None
    model_metadata: Optional[ModelMetadata] = None

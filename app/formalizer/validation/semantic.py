"""
Semantic Validator

Traverses the AST and verifies:
  - Every variable exists in the ontology.
  - Operators are allowed for that variable's type.
  - Values match the expected type (no age >= "male").
  - Boolean variables have boolean values.
  - Unresolved nodes pass through unchanged.

Invalid nodes are converted to UnresolvedNode (not silently dropped).
A warning is appended for each conversion.
"""
from typing import List, Tuple
from app.schema.ast import (
    ASTNode, ComparisonNode, BooleanNode, MembershipNode,
    TemporalNode, UnresolvedNode, AndNode, OrNode, NotNode,
)
from app.ontology.variables import registry, VariableType
from app.models.errors import ErrorCode, FormalizerError


class SemanticValidator:

    def validate(self, node: ASTNode) -> Tuple[ASTNode, List[FormalizerError]]:
        """
        Recursively validate the AST.
        Returns (validated_node, list_of_errors).
        Any node that fails validation is replaced with an UnresolvedNode.
        """
        errors: List[FormalizerError] = []
        result = self._validate_node(node, errors)
        return result, errors

    # ── Dispatcher ─────────────────────────────────────────────────────────────

    def _validate_node(self, node: ASTNode, errors: List[FormalizerError]) -> ASTNode:
        t = node.type
        if t == "unresolved":
            return node
        if t == "comparison":
            return self._check_comparison(node, errors)
        if t == "boolean":
            return self._check_boolean(node, errors)
        if t == "membership":
            return self._check_membership(node, errors)
        if t == "temporal":
            return node  # temporal nodes pass through; handled by downstream
        if t == "and":
            node.conditions = [self._validate_node(c, errors) for c in node.conditions]
            return node
        if t == "or":
            node.conditions = [self._validate_node(c, errors) for c in node.conditions]
            return node
        if t == "not":
            node.condition = self._validate_node(node.condition, errors)
            return node
        # Unknown type
        err = FormalizerError(
            code=ErrorCode.SCHEMA_VALIDATION_ERROR,
            stage="semantic_validation",
            message=f"Unknown AST node type '{t}'.",
            source_text=node.source_text,
        )
        errors.append(err)
        return UnresolvedNode(source_text=node.source_text, reason=str(err))

    # ── Leaf validators ────────────────────────────────────────────────────────

    def _check_comparison(self, node: ComparisonNode, errors: List[FormalizerError]) -> ASTNode:
        var = registry.get(node.variable)
        if var is None:
            err = FormalizerError(
                code=ErrorCode.UNKNOWN_VARIABLE, stage="semantic_validation",
                message=f"Variable '{node.variable}' not found in ontology.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        node.variable = var.name  # canonicalize

        if node.operator.value not in var.allowed_operators:
            err = FormalizerError(
                code=ErrorCode.OPERATOR_NOT_ALLOWED, stage="semantic_validation",
                message=f"Operator '{node.operator.value}' not allowed for '{var.name}'. "
                        f"Allowed: {var.allowed_operators}",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        if not self._type_matches(node.value, var.type):
            err = FormalizerError(
                code=ErrorCode.TYPE_MISMATCH, stage="semantic_validation",
                message=f"Value '{node.value}' ({type(node.value).__name__}) "
                        f"is incompatible with type {var.type.value} for variable '{var.name}'.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        return node

    def _check_boolean(self, node: BooleanNode, errors: List[FormalizerError]) -> ASTNode:
        var = registry.get(node.variable)
        if var is None:
            err = FormalizerError(
                code=ErrorCode.UNKNOWN_VARIABLE, stage="semantic_validation",
                message=f"Variable '{node.variable}' not found in ontology.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        node.variable = var.name

        if var.type != VariableType.BOOLEAN:
            err = FormalizerError(
                code=ErrorCode.TYPE_MISMATCH, stage="semantic_validation",
                message=f"Variable '{var.name}' has type {var.type.value}, not BOOLEAN.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        return node

    def _check_membership(self, node: MembershipNode, errors: List[FormalizerError]) -> ASTNode:
        var = registry.get(node.variable)
        if var is None:
            err = FormalizerError(
                code=ErrorCode.UNKNOWN_VARIABLE, stage="semantic_validation",
                message=f"Variable '{node.variable}' not found in ontology.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        node.variable = var.name
        if "IN" not in var.allowed_operators:
            err = FormalizerError(
                code=ErrorCode.OPERATOR_NOT_ALLOWED, stage="semantic_validation",
                message=f"Operator 'IN' not allowed for '{var.name}'.",
                source_text=node.source_text,
            )
            errors.append(err)
            return UnresolvedNode(source_text=node.source_text, reason=str(err))

        return node

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _type_matches(value, vtype: VariableType) -> bool:
        if vtype == VariableType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if vtype == VariableType.REAL:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if vtype == VariableType.BOOLEAN:
            return isinstance(value, bool)
        if vtype == VariableType.STRING:
            return isinstance(value, str)
        return True  # DATE / SET — pass through for now

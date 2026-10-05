"""
Deterministic SMT-LIB Generator

Takes ONLY a validated ASTNode (post semantic validation) and produces
well-formed SMT-LIB 2.6 text.

Rules:
  - No LLM involvement whatsoever.
  - Every node type maps to a deterministic SMT fragment.
  - Unresolved or temporal nodes cause PARTIAL status (excluded from SMT).
  - String variables use Z3 String sort; booleans use Bool; ints use Int.
"""
from typing import Set, List, Tuple
from app.schema.ast import (
    ASTNode, ComparisonNode, BooleanNode, MembershipNode,
    TemporalNode, UnresolvedNode, AndNode, OrNode, NotNode,
)
from app.ontology.variables import registry, VariableType


class SMTGenerationError(Exception):
    pass


class SMTGenerator:

    def generate(self, node: ASTNode) -> Tuple[str, bool]:
        """
        Returns (smt_lib_string, is_complete).
        is_complete=False means some nodes were unresolved/temporal and skipped.
        """
        variables: Set[str] = set()
        self._collect_variables(node, variables)

        declarations: List[str] = []
        for var_name in sorted(variables):
            var_info = registry.get(var_name)
            if not var_info:
                raise SMTGenerationError(f"Unknown variable in SMT generation: {var_name}")
            smt_type = self._smt_type(var_info.type)
            declarations.append(f"(declare-const {var_name} {smt_type})")

        expr, is_complete = self._node_to_expr(node)

        if not expr:
            return "; No SMT assertions generated (all criteria unresolved).", False

        # Wrap in a single (assert ...) when the top-level is a conjunction
        smt_lines = declarations + [f"(assert {expr})"]
        return "\n".join(smt_lines), is_complete

    # ── Variable collection ────────────────────────────────────────────────────

    def _collect_variables(self, node: ASTNode, acc: Set[str]) -> None:
        t = node.type
        if t in ("comparison", "boolean", "membership"):
            acc.add(node.variable)
        elif t in ("and", "or"):
            for c in node.conditions:
                self._collect_variables(c, acc)
        elif t == "not":
            self._collect_variables(node.condition, acc)
        # unresolved / temporal: no variables added

    # ── Expression builder ─────────────────────────────────────────────────────

    def _node_to_expr(self, node: ASTNode) -> Tuple[str, bool]:
        """Returns (smt_expression, is_complete)."""
        t = node.type

        if t == "unresolved":
            return "", False   # skip — contributes to PARTIAL status

        if t == "temporal":
            return "", False   # temporal not yet supported in SMT

        if t == "comparison":
            return self._comparison_expr(node), True

        if t == "boolean":
            val = "true" if node.value else "false"
            return f"(= {node.variable} {val})", True

        if t == "membership":
            # Expand IN to (or (= var v1) (= var v2) ...)
            clauses = [f'(= {node.variable} "{v}")' for v in node.values]
            if len(clauses) == 1:
                return clauses[0], True
            return f"(or {' '.join(clauses)})", True

        if t == "and":
            parts, complete = self._multi_expr(node.conditions)
            if not parts:
                return "", False
            if len(parts) == 1:
                return parts[0], complete
            return f"(and {' '.join(parts)})", complete

        if t == "or":
            parts, complete = self._multi_expr(node.conditions)
            if not parts:
                return "", False
            if len(parts) == 1:
                return parts[0], complete
            return f"(or {' '.join(parts)})", complete

        if t == "not":
            inner, complete = self._node_to_expr(node.condition)
            if not inner:
                return "", False
            return f"(not {inner})", complete

        raise SMTGenerationError(f"Cannot generate SMT for unknown node type '{t}'")

    def _multi_expr(self, conditions: list) -> Tuple[List[str], bool]:
        parts = []
        complete = True
        for c in conditions:
            expr, ok = self._node_to_expr(c)
            if expr:
                parts.append(expr)
            if not ok:
                complete = False
        return parts, complete

    def _comparison_expr(self, node: ComparisonNode) -> str:
        op = node.operator.value
        val = node.value

        # Format value correctly for SMT
        if isinstance(val, bool):
            formatted = "true" if val else "false"
        elif isinstance(val, str):
            formatted = f'"{val}"'
        else:
            formatted = str(val)

        smt_op = {
            "==": "=",
            "!=": None,   # handled specially
            ">":  ">",
            ">=": ">=",
            "<":  "<",
            "<=": "<=",
        }.get(op)

        if smt_op is None:  # !=
            return f"(not (= {node.variable} {formatted}))"

        return f"({smt_op} {node.variable} {formatted})"

    # ── Type mapping ───────────────────────────────────────────────────────────

    @staticmethod
    def _smt_type(vtype: VariableType) -> str:
        mapping = {
            VariableType.INTEGER: "Int",
            VariableType.REAL:    "Real",
            VariableType.BOOLEAN: "Bool",
            VariableType.STRING:  "String",
            VariableType.DATE:    "String",  # dates as strings for now
            VariableType.SET:     "String",
        }
        result = mapping.get(vtype)
        if result is None:
            raise SMTGenerationError(f"No SMT type mapping for {vtype}")
        return result

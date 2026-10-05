"""
Unit tests for the deterministic (non-LLM) components:
  - AST parsing via Pydantic TypeAdapter
  - Semantic validation (variable lookup, type checks, operator checks)
  - SMT-LIB generation
  - Z3 verification

These tests do NOT call the Gemini API — they operate on pre-defined ASTs
from the gold and adversarial datasets.
"""
import json
import os
import pytest
from pydantic import TypeAdapter

from app.schema.ast import ASTNode, UnresolvedNode
from app.formalizer.validation.semantic import SemanticValidator
from app.formalizer.smt.generator import SMTGenerator
from app.formalizer.z3.verifier import Z3Verifier

# ── Helpers ────────────────────────────────────────────────────────────────────

adapter   = TypeAdapter(ASTNode)
validator = SemanticValidator()
smt_gen   = SMTGenerator()
z3        = Z3Verifier()

TESTS_DIR = os.path.dirname(__file__)


def load(filename: str):
    with open(os.path.join(TESTS_DIR, filename)) as f:
        return json.load(f)


def parse_ast(d: dict) -> ASTNode:
    return adapter.validate_python(d)


# ── Gold dataset: schema + validation + SMT + Z3 ──────────────────────────────

@pytest.mark.parametrize("case", load("dataset_gold.json"), ids=[c["id"] for c in load("dataset_gold.json")])
def test_gold_pipeline(case):
    """
    Every gold case must:
    1. Parse into a typed ASTNode.
    2. Pass semantic validation (or stay unresolved if expected).
    3. Generate syntactically correct SMT-LIB.
    4. Be accepted by Z3 (SAT or UNSAT, not ERROR).
    """
    node = parse_ast(case["expected_ast"])
    validated, errors = validator.validate(node)

    if case["expected_ast"]["type"] == "unresolved":
        assert validated.type == "unresolved", (
            f"{case['id']}: expected unresolved, got {validated.type}"
        )
        return  # No SMT for unresolved

    assert validated.type != "unresolved", (
        f"{case['id']}: unexpected unresolved — {[str(e) for e in errors]}"
    )

    # temporal nodes: SMT not yet supported, but no crash
    if validated.type == "temporal":
        return

    smt_str, _ = smt_gen.generate(validated)
    # Must produce some output
    assert smt_str and not smt_str.startswith("; No SMT"), \
        f"{case['id']}: SMT generator produced no output"

    status, msg = z3.verify(smt_str)
    assert status != "ERROR", \
        f"{case['id']}: Z3 rejected generated SMT — {msg}\nSMT:\n{smt_str}"


# ── Negation correctness ───────────────────────────────────────────────────────

NEGATION_IDS = {
    "gold_08", "gold_09", "gold_10", "gold_11",
    "gold_12", "gold_13", "gold_14",
    "adv_05",  "adv_06",  "adv_07",  "adv_08",  "adv_09",
}


@pytest.mark.parametrize("case", [c for c in load("dataset_gold.json") if c["id"] in NEGATION_IDS] +
                                   [c for c in load("dataset_adversarial.json") if c["id"] in NEGATION_IDS],
                          ids=lambda c: c["id"])
def test_negation_preserved(case):
    """Negated criteria must NOT produce value=True for the negated variable."""
    node = parse_ast(case["expected_ast"])
    validated, _ = validator.validate(node)

    if validated.type == "boolean":
        assert validated.value is False, (
            f"{case['id']}: negation dropped! Got value=True, expected False."
        )
    elif validated.type == "not":
        pass  # NOT wrapper is also acceptable
    elif validated.type == "unresolved":
        pytest.skip("Node is unresolved — negation test not applicable")


# ── Operator boundary tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("case", load("dataset_adversarial.json"), ids=[c["id"] for c in load("dataset_adversarial.json")])
def test_adversarial(case):
    """Adversarial cases: verify that the expected AST parses and compiles correctly."""
    node = parse_ast(case["expected_ast"])
    validated, errors = validator.validate(node)

    if case["expected_ast"]["type"] == "unresolved":
        assert validated.type == "unresolved", \
            f"{case['id']}: expected unresolved, got {validated.type}"
        return

    if validated.type == "temporal":
        return

    # Check that no wrong_would_be situation exists
    if "wrong_would_be" in case:
        wrong = case["wrong_would_be"]
        if "operator" in wrong and validated.type == "comparison":
            assert validated.operator.value != wrong["operator"], \
                f"{case['id']}: wrong operator! Got {validated.operator.value}, forbidden {wrong['operator']}"
        if "value" in wrong and validated.type == "boolean":
            assert validated.value != wrong["value"], \
                f"{case['id']}: negation failure! Got value={validated.value}, forbidden value={wrong['value']}"
        if "type" in wrong:
            assert validated.type != wrong["type"], \
                f"{case['id']}: wrong node type! Got {validated.type}, forbidden {wrong['type']}"

    smt_str, _ = smt_gen.generate(validated)
    status, msg = z3.verify(smt_str)
    assert status != "ERROR", f"{case['id']}: Z3 error — {msg}"


# ── SMT determinism test ───────────────────────────────────────────────────────

def test_smt_determinism():
    """The same AST must produce the same SMT string every time."""
    ast_dict = {"type": "comparison", "variable": "age", "operator": ">=",
                "value": 18, "unit": "years", "source_text": "at least 18"}
    node = parse_ast(ast_dict)
    validated, _ = validator.validate(node)
    smt1, _ = smt_gen.generate(validated)
    smt2, _ = smt_gen.generate(validated)
    assert smt1 == smt2, "SMT generation is not deterministic!"


# ── Type rejection test ────────────────────────────────────────────────────────

def test_type_mismatch_rejected():
    """age >= 'male' must be rejected by the semantic validator."""
    ast_dict = {"type": "comparison", "variable": "age", "operator": ">=",
                "value": "male", "source_text": "age >= male"}
    node = parse_ast(ast_dict)
    validated, errors = validator.validate(node)
    assert validated.type == "unresolved", \
        f"TYPE_MISMATCH not caught! Got {validated.type}"
    assert any(e.code.value == "TYPE_MISMATCH" for e in errors), \
        "Expected TYPE_MISMATCH error code"


# ── Unknown variable rejection ─────────────────────────────────────────────────

def test_unknown_variable_rejected():
    """A made-up variable must be rejected."""
    ast_dict = {"type": "comparison", "variable": "invented_biomarker",
                "operator": ">=", "value": 5, "source_text": "invented_biomarker >= 5"}
    node = parse_ast(ast_dict)
    validated, errors = validator.validate(node)
    assert validated.type == "unresolved", \
        f"Unknown variable not caught! Got {validated.type}"
    assert any(e.code.value == "UNKNOWN_VARIABLE" for e in errors)


# ── Operator rejection test ────────────────────────────────────────────────────

def test_disallowed_operator_rejected():
    """egfr_positive >= 1 must be rejected (only == is allowed for booleans)."""
    ast_dict = {"type": "comparison", "variable": "egfr_positive",
                "operator": ">=", "value": 1, "source_text": "egfr_positive >= 1"}
    node = parse_ast(ast_dict)
    validated, errors = validator.validate(node)
    assert validated.type == "unresolved"

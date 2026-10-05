"""
Central Autoformalizer Pipeline.

Stages:
  1. (Optional) cache lookup
  2. LLM extraction (GeminiProvider → ASTNode)
  3. Semantic validation (ontology checks, type checks)
  4. SMT-LIB generation (deterministic)
  5. Z3 verification (syntax + satisfiability)
  6. Construct TrialFormalization result
  7. (Optional) cache save

Inclusion / Exclusion are handled separately:
  - Inclusion text → formalized as-is.
  - Exclusion text → formalized, then wrapped in NOT().
  - Both combined with AND().
"""
from __future__ import annotations
import hashlib
import time
from typing import Optional, List, Literal

from app.schema.ast import (
    ASTNode, AndNode, NotNode, UnresolvedNode,
    TrialFormalization, CriterionResult, ValidationResult, ModelMetadata,
)
from app.formalizer.llm.base import LLMProvider, LLMError
from app.formalizer.llm.gemini import GeminiProvider
from app.formalizer.validation.semantic import SemanticValidator
from app.formalizer.smt.generator import SMTGenerator
from app.formalizer.z3.verifier import Z3Verifier
from app.cache.manager import CacheManager
from app.models.errors import FormalizerError
from app.config import settings


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class AutoformalizerPipeline:
    def __init__(self, llm: Optional[LLMProvider] = None) -> None:
        self.llm       = llm or GeminiProvider()
        self.validator = SemanticValidator()
        self.smt_gen   = SMTGenerator()
        self.z3        = Z3Verifier()
        self.cache     = CacheManager()

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(
        self,
        trial_id: str,
        inclusion_text: Optional[str] = None,
        exclusion_text: Optional[str] = None,
        use_cache: bool = True,
    ) -> TrialFormalization:
        combined_text = self._combined_text(inclusion_text, exclusion_text)
        input_hash = _hash_text(combined_text)
        t0 = time.time()

        if use_cache:
            cached = self.cache.get_cached(trial_id, combined_text)
            if cached:
                return cached

        all_errors:   List[FormalizerError] = []
        all_warnings: List[str] = []
        criteria:     List[CriterionResult] = []
        unresolved:   List[UnresolvedNode]  = []

        # ── Formalize inclusion ────────────────────────────────────────────────
        incl_ast: Optional[ASTNode] = None
        if inclusion_text and inclusion_text.strip():
            incl_ast, errs = self._formalize_clause(
                inclusion_text.strip(), "inclusion", criteria, unresolved
            )
            all_errors.extend(errs)

        # ── Formalize exclusion ────────────────────────────────────────────────
        excl_ast: Optional[ASTNode] = None
        if exclusion_text and exclusion_text.strip():
            raw_excl, errs = self._formalize_clause(
                exclusion_text.strip(), "exclusion", criteria, unresolved
            )
            all_errors.extend(errs)
            # Wrap exclusion in NOT — but only if we got something meaningful
            if raw_excl and raw_excl.type != "unresolved":
                excl_ast = NotNode(
                    condition=raw_excl,
                    source_text=f"NOT({exclusion_text.strip()})",
                )
            elif raw_excl:
                excl_ast = raw_excl  # already unresolved — propagate

        # ── Combine inclusion + exclusion ──────────────────────────────────────
        formal_ast = self._combine(incl_ast, excl_ast, combined_text)

        if formal_ast is None:
            return self._build_result(
                trial_id=trial_id, status="FAILED",
                formal_ast=None, smt_lib=None,
                criteria=criteria, unresolved=unresolved,
                errors=all_errors, warnings=["No criteria could be formalized."],
                validation=None, input_hash=input_hash, latency_ms=_ms(t0),
            )

        # ── SMT Generation ─────────────────────────────────────────────────────
        try:
            smt_lib, is_complete = self.smt_gen.generate(formal_ast)
        except Exception as e:
            return self._build_result(
                trial_id=trial_id, status="FAILED",
                formal_ast=formal_ast, smt_lib=None,
                criteria=criteria, unresolved=unresolved,
                errors=all_errors, warnings=[f"SMT generation error: {e}"],
                validation=None, input_hash=input_hash, latency_ms=_ms(t0),
            )

        # ── Z3 Verification ────────────────────────────────────────────────────
        z3_status, z3_msg = self.z3.verify(smt_lib)
        all_warnings.append(f"Z3: {z3_status} — {z3_msg}")

        if z3_status == "ERROR":
            return self._build_result(
                trial_id=trial_id, status="FAILED",
                formal_ast=formal_ast, smt_lib=smt_lib,
                criteria=criteria, unresolved=unresolved,
                errors=all_errors, warnings=all_warnings,
                validation=ValidationResult(passed=False, errors=[z3_msg]),
                input_hash=input_hash, latency_ms=_ms(t0),
            )

        # ── Determine overall status ───────────────────────────────────────────
        has_unresolved = bool(unresolved)
        status: Literal["SUCCESS", "PARTIAL", "FAILED"] = (
            "PARTIAL" if (has_unresolved or not is_complete) else "SUCCESS"
        )

        result = self._build_result(
            trial_id=trial_id, status=status,
            formal_ast=formal_ast, smt_lib=smt_lib,
            criteria=criteria, unresolved=unresolved,
            errors=all_errors, warnings=all_warnings,
            validation=ValidationResult(
                passed=True,
                warnings=[str(e) for e in all_errors],
            ),
            input_hash=input_hash, latency_ms=_ms(t0),
        )

        if use_cache and status != "FAILED":
            self.cache.save(result, combined_text)

        return result

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _formalize_clause(
        self,
        text: str,
        criterion_type: Literal["inclusion", "exclusion"],
        criteria: List[CriterionResult],
        unresolved: List[UnresolvedNode],
    ):
        errors: List[FormalizerError] = []
        try:
            raw_ast = self.llm.extract_ast(text)
        except LLMError as e:
            node = UnresolvedNode(source_text=text, reason=str(e))
            unresolved.append(node)
            criteria.append(CriterionResult(
                source_text=text, criterion_type=criterion_type,
                status="unresolved", reason=str(e),
            ))
            return node, errors

        validated_ast, val_errors = self.validator.validate(raw_ast)
        errors.extend(val_errors)

        if validated_ast.type == "unresolved":
            unresolved.append(validated_ast)
            criteria.append(CriterionResult(
                source_text=text, criterion_type=criterion_type,
                status="unresolved", reason=validated_ast.reason, ast=validated_ast,
            ))
        else:
            criteria.append(CriterionResult(
                source_text=text, criterion_type=criterion_type,
                status="resolved", ast=validated_ast,
            ))
            # Collect any unresolved sub-nodes (partial)
            self._collect_unresolved(validated_ast, unresolved)

        return validated_ast, errors

    def _collect_unresolved(self, node: ASTNode, acc: List[UnresolvedNode]) -> None:
        if node.type == "unresolved":
            acc.append(node)
        elif node.type in ("and", "or"):
            for c in node.conditions:
                self._collect_unresolved(c, acc)
        elif node.type == "not":
            self._collect_unresolved(node.condition, acc)

    @staticmethod
    def _combine(
        incl: Optional[ASTNode], excl: Optional[ASTNode], source_text: str
    ) -> Optional[ASTNode]:
        parts = [n for n in [incl, excl] if n is not None]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return AndNode(conditions=parts, source_text=source_text)

    @staticmethod
    def _combined_text(incl: Optional[str], excl: Optional[str]) -> str:
        parts = []
        if incl:
            parts.append(f"INCLUSION: {incl.strip()}")
        if excl:
            parts.append(f"EXCLUSION: {excl.strip()}")
        return " | ".join(parts)

    def _build_result(
        self, *, trial_id, status, formal_ast, smt_lib,
        criteria, unresolved, errors, warnings, validation,
        input_hash, latency_ms,
    ) -> TrialFormalization:
        required_vars: List[str] = []
        if formal_ast and formal_ast.type not in ("unresolved", "temporal"):
            try:
                vars_set: set = set()
                self.smt_gen._collect_variables(formal_ast, vars_set)
                required_vars = sorted(vars_set)
            except Exception:
                pass

        return TrialFormalization(
            trial_id=trial_id,
            status=status,
            formal_ast=formal_ast,
            smt_lib=smt_lib,
            required_variables=required_vars,
            criteria=criteria,
            unresolved_items=unresolved,
            warnings=warnings,
            errors=[str(e) for e in errors],
            validation=validation,
            model_metadata=ModelMetadata(
                model=self.llm.model_name,
                temperature=settings.GEMINI_TEMPERATURE,
                prompt_version=settings.PROMPT_VERSION,
                schema_version=settings.SCHEMA_VERSION,
                ontology_version=settings.ONTOLOGY_VERSION,
                formalizer_version=settings.FORMALIZER_VERSION,
                input_hash=input_hash,
                latency_ms=latency_ms,
            ),
        )


def _ms(t0: float) -> float:
    return round((time.time() - t0) * 1000, 1)

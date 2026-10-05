"""
FastAPI Backend — Autoformalizer REST API

Endpoints:
  POST /formalize              — formalize a trial's eligibility criteria
  GET  /formalization/{trial_id} — retrieve cached result
  POST /formalize/validate     — validate (dry-run, no cache write)
  POST /formalize/batch        — batch multiple trials
  GET  /health                 — liveness check
"""
from __future__ import annotations
from typing import List, Optional
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.schema.ast import TrialFormalization
from app.formalizer.pipeline import AutoformalizerPipeline
from app.cache.manager import CacheManager

app = FastAPI(
    title="Autoformalizer API",
    description="Converts clinical-trial eligibility text to formal SMT-LIB constraints.",
    version="1.0.0",
)

_pipeline = AutoformalizerPipeline()
_cache    = CacheManager()


# ── Request / response models ──────────────────────────────────────────────────

class FormalizationRequest(BaseModel):
    trial_id: str
    inclusion_text: Optional[str] = None
    exclusion_text: Optional[str] = None


class BatchFormalizationRequest(BaseModel):
    trials: List[FormalizationRequest]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/formalize", response_model=TrialFormalization, tags=["formalize"])
def formalize(request: FormalizationRequest):
    """Formalize a trial's eligibility criteria and cache the result."""
    if not request.inclusion_text and not request.exclusion_text:
        raise HTTPException(
            status_code=400, detail="Must provide inclusion_text or exclusion_text."
        )
    return _pipeline.process(
        trial_id=request.trial_id,
        inclusion_text=request.inclusion_text,
        exclusion_text=request.exclusion_text,
        use_cache=True,
    )


@app.get("/formalization/{trial_id}", response_model=TrialFormalization, tags=["formalize"])
def get_formalization(trial_id: str, inclusion_text: str = "", exclusion_text: str = ""):
    """Retrieve a cached formalization for a trial ID."""
    combined = ""
    if inclusion_text:
        combined += f"INCLUSION: {inclusion_text.strip()}"
    if exclusion_text:
        combined += f" | EXCLUSION: {exclusion_text.strip()}"
    result = _cache.get_cached(trial_id, combined or trial_id)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"No cached formalization for trial '{trial_id}'."
        )
    return result


@app.post("/formalize/validate", response_model=TrialFormalization, tags=["formalize"])
def validate_formalization(request: FormalizationRequest):
    """Validate a formalization without writing to the cache."""
    if not request.inclusion_text and not request.exclusion_text:
        raise HTTPException(
            status_code=400, detail="Must provide inclusion_text or exclusion_text."
        )
    return _pipeline.process(
        trial_id=request.trial_id,
        inclusion_text=request.inclusion_text,
        exclusion_text=request.exclusion_text,
        use_cache=False,
    )


@app.post("/formalize/batch", response_model=List[TrialFormalization], tags=["formalize"])
def batch_formalize(request: BatchFormalizationRequest):
    """Formalize multiple trials in sequence."""
    if not request.trials:
        raise HTTPException(status_code=400, detail="No trials provided.")
    results = []
    for trial in request.trials:
        result = _pipeline.process(
            trial_id=trial.trial_id,
            inclusion_text=trial.inclusion_text,
            exclusion_text=trial.exclusion_text,
            use_cache=True,
        )
        results.append(result)
    return results


@app.get("/health", tags=["meta"])
def health():
    return {"status": "healthy", "version": "1.0.0"}

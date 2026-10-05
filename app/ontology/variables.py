"""
Controlled Clinical Variable Registry.

Every variable has:
  - canonical name
  - type            (INTEGER | REAL | BOOLEAN | STRING | DATE | SET)
  - description
  - allowed_operators
  - unit            (optional)
  - synonyms        (all lower-case for matching)
  - category

Covers all 30+ variables required by the spec:
  DEMOGRAPHICS, DISEASE, BIOMARKERS, PERFORMANCE,
  LABORATORY, TREATMENT HISTORY, MEDICATION, DATES
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel


class VariableType(str, Enum):
    INTEGER  = "INTEGER"
    REAL     = "REAL"
    BOOLEAN  = "BOOLEAN"
    STRING   = "STRING"
    DATE     = "DATE"
    SET      = "SET"


class ClinicalVariable(BaseModel):
    name: str
    type: VariableType
    description: str
    allowed_operators: List[str]
    unit: Optional[str] = None
    synonyms: List[str] = []
    category: str


class VariableRegistry:
    def __init__(self) -> None:
        self._by_canonical: Dict[str, ClinicalVariable] = {}
        self._synonym_map: Dict[str, str] = {}   # synonym -> canonical name

    def register(self, var: ClinicalVariable) -> None:
        self._by_canonical[var.name] = var
        # Map every synonym (including the canonical name itself) to canonical
        for syn in [var.name] + [s.lower() for s in var.synonyms]:
            self._synonym_map[syn.lower()] = var.name

    def get(self, name: str) -> Optional[ClinicalVariable]:
        canonical = self._synonym_map.get(name.strip().lower())
        if canonical:
            return self._by_canonical.get(canonical)
        return None

    def all_variables(self) -> List[ClinicalVariable]:
        return list(self._by_canonical.values())

    def to_prompt_context(self) -> str:
        """Human-readable block sent to the LLM as the variable ontology."""
        lines = []
        current_cat = None
        for var in sorted(self._by_canonical.values(), key=lambda v: v.category):
            if var.category != current_cat:
                current_cat = var.category
                lines.append(f"\n## {current_cat.upper()}")
            ops = ", ".join(var.allowed_operators)
            syns = ", ".join(var.synonyms[:4]) if var.synonyms else "—"
            unit = f" [{var.unit}]" if var.unit else ""
            lines.append(
                f"  - {var.name} ({var.type.value}{unit}): {var.description}"
                f" | operators: {ops} | synonyms: {syns}"
            )
        return "\n".join(lines)


# ── Singleton registry ─────────────────────────────────────────────────────────
registry = VariableRegistry()

# ╔══════════════════════════════════════════════════╗
# ║  DEMOGRAPHICS                                    ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="age", type=VariableType.INTEGER,
    description="Patient age in years",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="years",
    synonyms=["age", "patient age", "years old", "years of age"],
    category="demographics",
))
registry.register(ClinicalVariable(
    name="sex", type=VariableType.STRING,
    description="Patient biological sex (male | female)",
    allowed_operators=["==", "!="],
    synonyms=["sex", "gender", "biological sex"],
    category="demographics",
))
registry.register(ClinicalVariable(
    name="pregnancy_status", type=VariableType.BOOLEAN,
    description="Whether the patient is currently pregnant",
    allowed_operators=["=="],
    synonyms=["pregnant", "pregnancy", "pregnancy status", "gravid"],
    category="demographics",
))

# ╔══════════════════════════════════════════════════╗
# ║  DISEASE                                         ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="cancer_type", type=VariableType.STRING,
    description="Histological cancer type (e.g. NSCLC, SCLC)",
    allowed_operators=["==", "!=", "IN"],
    synonyms=["cancer type", "tumor type", "histology", "cancer diagnosis",
              "non-small cell lung cancer", "nsclc", "sclc", "small cell lung cancer"],
    category="disease",
))
registry.register(ClinicalVariable(
    name="disease_stage", type=VariableType.STRING,
    description="Disease stage (I, II, III, IV, or sub-stages)",
    allowed_operators=["==", "!=", "IN"],
    synonyms=["stage", "disease stage", "tumor stage", "cancer stage"],
    category="disease",
))
registry.register(ClinicalVariable(
    name="diagnosis", type=VariableType.STRING,
    description="Primary diagnosis",
    allowed_operators=["==", "!="],
    synonyms=["diagnosis", "primary diagnosis", "condition"],
    category="disease",
))
registry.register(ClinicalVariable(
    name="metastasis", type=VariableType.BOOLEAN,
    description="Presence of metastatic disease",
    allowed_operators=["=="],
    synonyms=["metastasis", "metastatic", "metastatic disease", "distant metastasis",
              "stage iv", "advanced disease"],
    category="disease",
))

# ╔══════════════════════════════════════════════════╗
# ║  BIOMARKERS                                      ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="egfr_positive", type=VariableType.BOOLEAN,
    description="EGFR mutation positive status",
    allowed_operators=["=="],
    synonyms=["egfr", "egfr positive", "egfr mutation", "egfr-positive",
              "egfr mutation positive", "egfr status"],
    category="biomarkers",
))
registry.register(ClinicalVariable(
    name="alk_positive", type=VariableType.BOOLEAN,
    description="ALK rearrangement positive status",
    allowed_operators=["=="],
    synonyms=["alk", "alk positive", "alk rearrangement", "alk-positive", "alk fusion"],
    category="biomarkers",
))
registry.register(ClinicalVariable(
    name="her2_positive", type=VariableType.BOOLEAN,
    description="HER2 overexpression positive status",
    allowed_operators=["=="],
    synonyms=["her2", "her2 positive", "her-2", "erbb2", "her2/neu"],
    category="biomarkers",
))
registry.register(ClinicalVariable(
    name="pd_l1_level", type=VariableType.REAL,
    description="PD-L1 expression level as percentage",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="%",
    synonyms=["pd-l1", "pd l1", "pdl1", "pd-l1 expression", "pd-l1 level"],
    category="biomarkers",
))

# ╔══════════════════════════════════════════════════╗
# ║  PERFORMANCE STATUS                              ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="ecog_status", type=VariableType.INTEGER,
    description="ECOG performance status (0–5)",
    allowed_operators=["==", "<=", ">=", "<", ">"],
    synonyms=["ecog", "ecog status", "ecog performance", "performance status",
              "ecog ps", "ps", "eastern cooperative oncology group"],
    category="performance",
))
registry.register(ClinicalVariable(
    name="karnofsky_score", type=VariableType.INTEGER,
    description="Karnofsky performance score (0–100)",
    allowed_operators=[">=", "<=", ">", "<", "=="],
    unit="%",
    synonyms=["karnofsky", "kps", "karnofsky score", "karnofsky performance"],
    category="performance",
))

# ╔══════════════════════════════════════════════════╗
# ║  LABORATORY                                      ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="hemoglobin", type=VariableType.REAL,
    description="Hemoglobin level",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="g/dL",
    synonyms=["hemoglobin", "hgb", "hb", "haemoglobin"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="platelets", type=VariableType.REAL,
    description="Platelet count",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="cells/uL",
    synonyms=["platelets", "platelet count", "plt", "thrombocytes"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="neutrophils", type=VariableType.REAL,
    description="Absolute neutrophil count",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="cells/uL",
    synonyms=["neutrophils", "anc", "absolute neutrophil count", "neutrophil count"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="creatinine", type=VariableType.REAL,
    description="Serum creatinine level",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="mg/dL",
    synonyms=["creatinine", "serum creatinine", "cr", "scr"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="bilirubin", type=VariableType.REAL,
    description="Total serum bilirubin level",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="mg/dL",
    synonyms=["bilirubin", "total bilirubin", "tbili", "tbil"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="ast_level", type=VariableType.REAL,
    description="Aspartate aminotransferase (AST) level",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="U/L",
    synonyms=["ast", "sgot", "aspartate aminotransferase", "ast level"],
    category="laboratory",
))
registry.register(ClinicalVariable(
    name="alt_level", type=VariableType.REAL,
    description="Alanine aminotransferase (ALT) level",
    allowed_operators=[">", ">=", "<", "<=", "=="],
    unit="U/L",
    synonyms=["alt", "sgpt", "alanine aminotransferase", "alt level"],
    category="laboratory",
))

# ╔══════════════════════════════════════════════════╗
# ║  TREATMENT HISTORY                               ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="prior_chemotherapy", type=VariableType.BOOLEAN,
    description="History of prior systemic chemotherapy",
    allowed_operators=["=="],
    synonyms=["prior chemotherapy", "previous chemotherapy", "chemotherapy history",
              "prior chemo", "chemo", "chemotherapy", "prior systemic therapy",
              "previously treated with chemotherapy"],
    category="treatment_history",
))
registry.register(ClinicalVariable(
    name="prior_radiation", type=VariableType.BOOLEAN,
    description="History of prior radiation therapy",
    allowed_operators=["=="],
    synonyms=["prior radiation", "previous radiation", "radiation therapy",
              "radiotherapy", "prior radiotherapy", "prior rt"],
    category="treatment_history",
))
registry.register(ClinicalVariable(
    name="prior_surgery", type=VariableType.BOOLEAN,
    description="History of prior surgical resection",
    allowed_operators=["=="],
    synonyms=["prior surgery", "previous surgery", "surgical resection",
              "prior resection", "surgery"],
    category="treatment_history",
))
registry.register(ClinicalVariable(
    name="prior_immunotherapy", type=VariableType.BOOLEAN,
    description="History of prior immunotherapy",
    allowed_operators=["=="],
    synonyms=["prior immunotherapy", "previous immunotherapy", "immunotherapy",
              "checkpoint inhibitor", "prior checkpoint inhibitor"],
    category="treatment_history",
))
registry.register(ClinicalVariable(
    name="prior_targeted_therapy", type=VariableType.BOOLEAN,
    description="History of prior targeted therapy",
    allowed_operators=["=="],
    synonyms=["prior targeted therapy", "targeted therapy", "prior tki",
              "tyrosine kinase inhibitor", "tki"],
    category="treatment_history",
))

# ╔══════════════════════════════════════════════════╗
# ║  DISEASE / CLINICAL CONDITIONS                   ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="active_infection", type=VariableType.BOOLEAN,
    description="Presence of an active systemic infection",
    allowed_operators=["=="],
    synonyms=["active infection", "infection", "systemic infection",
              "active bacterial infection", "active viral infection"],
    category="disease",
))
registry.register(ClinicalVariable(
    name="myocardial_infarction", type=VariableType.BOOLEAN,
    description="History of myocardial infarction (heart attack)",
    allowed_operators=["=="],
    synonyms=["myocardial infarction", "heart attack", "mi", "ami",
              "acute myocardial infarction", "prior mi"],
    category="disease",
))
registry.register(ClinicalVariable(
    name="brain_metastases", type=VariableType.BOOLEAN,
    description="Presence of brain metastases",
    allowed_operators=["=="],
    synonyms=["brain metastases", "brain mets", "cns metastases",
              "intracranial metastases", "cns mets"],
    category="disease",
))

# ╔══════════════════════════════════════════════════╗
# ║  MEDICATION                                      ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="current_medications", type=VariableType.STRING,
    description="Currently administered medications",
    allowed_operators=["==", "IN"],
    synonyms=["current medications", "current drugs", "medications", "current treatment"],
    category="medication",
))
registry.register(ClinicalVariable(
    name="prior_medications", type=VariableType.STRING,
    description="Previously administered medications",
    allowed_operators=["==", "IN"],
    synonyms=["prior medications", "previous medications", "prior drugs"],
    category="medication",
))

# ╔══════════════════════════════════════════════════╗
# ║  DATES                                           ║
# ╚══════════════════════════════════════════════════╝
registry.register(ClinicalVariable(
    name="diagnosis_date", type=VariableType.DATE,
    description="Date of initial diagnosis",
    allowed_operators=["==", "<", ">", "<=", ">="],
    synonyms=["diagnosis date", "date of diagnosis", "initial diagnosis"],
    category="dates",
))
registry.register(ClinicalVariable(
    name="treatment_date", type=VariableType.DATE,
    description="Date of treatment start",
    allowed_operators=["==", "<", ">", "<=", ">="],
    synonyms=["treatment date", "date of treatment", "treatment start"],
    category="dates",
))
registry.register(ClinicalVariable(
    name="last_therapy_date", type=VariableType.DATE,
    description="Date of last prior therapy",
    allowed_operators=["==", "<", ">", "<=", ">="],
    synonyms=["last therapy date", "last treatment date", "last chemotherapy date"],
    category="dates",
))
registry.register(ClinicalVariable(
    name="enrollment_date", type=VariableType.DATE,
    description="Date of trial enrollment",
    allowed_operators=["==", "<", ">", "<=", ">="],
    synonyms=["enrollment date", "date of enrollment", "study enrollment"],
    category="dates",
))

# Autoformalizer — Complete System Guide

## How to Run

### Step 1 — Setup (one time only)
```powershell
# In your terminal, inside the project folder:
cd C:\Users\amits\Downloads\Autoformalizer

# Activate the virtual environment
.venv\Scripts\activate

# Set your Gemini API key
$env:GEMINI_API_KEY = "your_gemini_api_key_here"
```

---

## Way 1 — Command Line Script (quickest demo)

```powershell
python examples/example_run.py
```

**What you input** (hardcoded in the script, edit to change):
```
"Patients must be at least 18 years old and have EGFR-positive NSCLC."
```

**What you get back:**
```
[Final Result Status]: SUCCESS
[AST Structure]: { "type": "and", "conditions": [...] }
[Required Variables]: ['age', 'cancer_type', 'egfr_positive']
[Z3 Status]: SAT
```

---

## Way 2 — Run the REST API

```powershell
uvicorn app.api.main:app --reload
```

Then open your browser at: **http://127.0.0.1:8000/docs**
You will see an interactive Swagger UI to test all 4 endpoints.

### Endpoint 1 — POST /formalize

**Input (JSON body):**
```json
{
  "trial_id": "NCT00012345",
  "inclusion_text": "Patients must be at least 18 years old and have EGFR-positive NSCLC.",
  "exclusion_text": "Patients who have received prior chemotherapy are excluded."
}
```

**Output (JSON response):**
```json
{
  "trial_id": "NCT00012345",
  "status": "SUCCESS",
  "formal_ast": {
    "type": "and",
    "conditions": [
      {
        "type": "and",
        "conditions": [
          { "type": "comparison", "variable": "age", "operator": ">=", "value": 18, "unit": "years", "source_text": "at least 18 years old" },
          { "type": "comparison", "variable": "cancer_type", "operator": "==", "value": "NSCLC", "source_text": "NSCLC" },
          { "type": "boolean", "variable": "egfr_positive", "value": true, "source_text": "EGFR-positive" }
        ]
      },
      {
        "type": "not",
        "condition": {
          "type": "boolean", "variable": "prior_chemotherapy", "value": true
        }
      }
    ]
  },
  "smt_lib": "(declare-const age Int)\n(declare-const cancer_type String)\n(declare-const egfr_positive Bool)\n(declare-const prior_chemotherapy Bool)\n(assert (and (and (>= age 18) (= cancer_type \"NSCLC\") (= egfr_positive true)) (not (= prior_chemotherapy true))))",
  "required_variables": ["age", "cancer_type", "egfr_positive", "prior_chemotherapy"],
  "criteria": [
    { "source_text": "Patients must be at least 18...", "criterion_type": "inclusion", "status": "resolved" },
    { "source_text": "Patients who have received prior chemotherapy are excluded.", "criterion_type": "exclusion", "status": "resolved" }
  ],
  "unresolved_items": [],
  "warnings": ["Z3: SAT — Constraints are satisfiable."],
  "errors": [],
  "validation": { "passed": true, "warnings": [], "errors": [] },
  "model_metadata": {
    "model": "gemini-2.0-flash",
    "temperature": 0.0,
    "prompt_version": "1.0",
    "schema_version": "1.0",
    "ontology_version": "1.0",
    "formalizer_version": "1.0.0",
    "input_hash": "a3f8b2c1d9e4",
    "latency_ms": 1234.5
  }
}
```

### Endpoint 2 — GET /formalization/{trial_id}
Retrieves a previously cached result (no Gemini call).

### Endpoint 3 — POST /formalize/validate
Same as /formalize but does NOT write to cache (for testing).

### Endpoint 4 — POST /formalize/batch
```json
{
  "trials": [
    { "trial_id": "NCT001", "inclusion_text": "..." },
    { "trial_id": "NCT002", "inclusion_text": "..." }
  ]
}
```

---

## Way 3 — Run Tests (no API key needed)

```powershell
pytest tests/test_logic.py -v
```

Tests 81 cases covering: AST parsing, semantic validation, SMT generation, Z3 verification,
negation correctness, operator boundaries, type rejection, unknown variable rejection.
**Expected: 81 passed**.

---

## Way 4 — Run Evaluation (requires API key)

```powershell
python evaluation/evaluator.py
```

Runs all 50 gold criteria through the full LLM pipeline and scores accuracy.

---

## Status Values Explained

| Status | Meaning |
|--------|---------|
| `SUCCESS` | Every criterion formalized. Z3 accepted the SMT. |
| `PARTIAL` | Some criteria formalized, some are UNRESOLVED (e.g. "adequate renal function"). |
| `FAILED` | Pipeline error: LLM failure, Z3 syntax error, all criteria unresolved. |

---

## PARTIAL Example

**Input:**
```json
{
  "trial_id": "NCT-PARTIAL",
  "inclusion_text": "Patients aged 18 or older with adequate renal function."
}
```

**Output:**
```json
{
  "status": "PARTIAL",
  "formal_ast": { "type": "and", "conditions": [ { "type": "comparison", "variable": "age", "operator": ">=", "value": 18 }, { "type": "unresolved", "reason": "No explicit measurable definition provided for adequate renal function." } ] },
  "unresolved_items": [ { "source_text": "adequate renal function", "reason": "No explicit measurable definition was provided." } ]
}
```

The system did NOT invent `creatinine < 1.5`.

---

## Data Flow Map — How Each Stage Transforms the Data

```
INPUT
──────────────────────────────────────────────────────────
{
  "trial_id": "NCT123",
  "inclusion_text": "Patients at least 18 years old.",
  "exclusion_text": "Prior chemotherapy excluded."
}

        │
        ▼
STAGE 1 — CACHE LOOKUP (app/cache/manager.py)
──────────────────────────────────────────────────────────
Key = SHA256(INCLUSION: ... | EXCLUSION: ...)
  HIT  → return cached TrialFormalization (skip all stages)
  MISS → continue to Stage 2


        │
        ▼
STAGE 2 — GEMINI LLM EXTRACTION (app/formalizer/llm/gemini.py)
──────────────────────────────────────────────────────────
Input  : raw inclusion text string
         "Patients at least 18 years old."

System : Gemini API with structured output schema (ASTNode)
         + full variable registry injected into prompt
         + 10 few-shot examples

Output : Pydantic ASTNode (raw, not yet validated)
{
  "type": "comparison",
  "variable": "age",
  "operator": ">=",
  "value": 18,
  "unit": "years",
  "source_text": "at least 18 years old"
}


        │
        ▼
STAGE 3 — SEMANTIC VALIDATION (app/formalizer/validation/semantic.py)
──────────────────────────────────────────────────────────
Checks each node against the Clinical Variable Ontology:

  ✅ variable "age" exists in registry?       → YES
  ✅ operator ">=" allowed for INTEGER?        → YES
  ✅ value 18 is correct type (int)?           → YES
  ✅ canonicalize name: "age" → "age"

If any check fails:
  → node converted to UnresolvedNode + FormalizerError logged

Output : Validated ASTNode (same structure, canonicalized names)


        │
        ▼
STAGE 4 — NOT() WRAPPING FOR EXCLUSION (app/formalizer/pipeline.py)
──────────────────────────────────────────────────────────
Exclusion text is formalized separately, then wrapped:

  raw exclusion AST:
    { "type": "boolean", "variable": "prior_chemotherapy", "value": true }

  wrapped:
    { "type": "not", "condition": { ... } }

Inclusion + wrapped exclusion combined with AND:
    { "type": "and", "conditions": [incl_ast, not_excl_ast] }


        │
        ▼
STAGE 5 — DETERMINISTIC SMT-LIB GENERATION (app/formalizer/smt/generator.py)
──────────────────────────────────────────────────────────
NO LLM INVOLVED. Pure code mapping.

AST Node          → SMT Fragment
─────────────────────────────────────────────────────────
comparison >=     → (>= age 18)
comparison ==     → (= cancer_type "NSCLC")
boolean true      → (= egfr_positive true)
boolean false     → (= prior_chemotherapy false)
membership IN     → (or (= cancer_type "NSCLC") (= cancer_type "SCLC"))
AndNode           → (and expr1 expr2 ...)
OrNode            → (or  expr1 expr2 ...)
NotNode           → (not expr)
unresolved        → skipped (marks result as PARTIAL)

Output:
(declare-const age Int)
(declare-const egfr_positive Bool)
(declare-const prior_chemotherapy Bool)
(assert (and (>= age 18) (= egfr_positive true) (not (= prior_chemotherapy true))))


        │
        ▼
STAGE 6 — Z3 VERIFICATION (app/formalizer/z3/verifier.py)
──────────────────────────────────────────────────────────
z3.parse_smt2_string(smt_lib)   ← syntax + type check
solver.check()                  ← satisfiability

Output:
  SAT     → constraints are mathematically consistent
  UNSAT   → constraints are self-contradictory (e.g. age >= 18 AND age < 10)
  UNKNOWN → solver timed out
  ERROR   → SMT syntax/type error (maps to FAILED status)


        │
        ▼
STAGE 7 — RESULT ASSEMBLY (app/formalizer/pipeline.py)
──────────────────────────────────────────────────────────
Combines everything into TrialFormalization:

  status            = SUCCESS / PARTIAL / FAILED
  formal_ast        = validated AST tree (JSON-serializable)
  smt_lib           = the generated SMT-LIB string
  required_variables= ["age", "egfr_positive", "prior_chemotherapy"]
  criteria          = list of per-criterion results with source_text
  unresolved_items  = list of UnresolvedNodes (if any)
  warnings          = Z3 status message
  errors            = machine-readable error codes
  validation        = { passed: true, warnings: [], errors: [] }
  model_metadata    = { model, temperature, latency_ms, input_hash, ... }


        │
        ▼
STAGE 8 — CACHE SAVE (app/cache/manager.py)
──────────────────────────────────────────────────────────
If status != FAILED:
  Store in SQLite keyed by:
  (trial_id, sha256(text), schema_version)

Next identical request → instant cache hit, no LLM call.


        │
        ▼
OUTPUT
──────────────────────────────────────────────────────────
TrialFormalization JSON returned to caller.
```

---

## Variable Registry — What the System Knows

The system can formalize criteria involving these 30+ variables:

| Category | Variables |
|----------|-----------|
| Demographics | `age`, `sex`, `pregnancy_status` |
| Disease | `cancer_type`, `disease_stage`, `diagnosis`, `metastasis`, `active_infection`, `myocardial_infarction`, `brain_metastases` |
| Biomarkers | `egfr_positive`, `alk_positive`, `her2_positive`, `pd_l1_level` |
| Performance | `ecog_status`, `karnofsky_score` |
| Laboratory | `hemoglobin`, `platelets`, `neutrophils`, `creatinine`, `bilirubin`, `ast_level`, `alt_level` |
| Treatment History | `prior_chemotherapy`, `prior_radiation`, `prior_surgery`, `prior_immunotherapy`, `prior_targeted_therapy` |
| Medication | `current_medications`, `prior_medications` |
| Dates | `diagnosis_date`, `treatment_date`, `last_therapy_date`, `enrollment_date` |

If a criterion mentions a variable NOT in this list → **UNRESOLVED** (never fabricated).

---

## What Happens With Ambiguous / Vague Criteria

| Input | System Output |
|-------|--------------|
| "Adequate renal function" | `UNRESOLVED` — no threshold defined |
| "Adequate hepatic function" | `UNRESOLVED` — no threshold defined |
| "At physician's discretion" | `UNRESOLVED` — not formally definable |
| "Clinically significant disease" | `UNRESOLVED` — no measurable definition |
| "AST < 3× ULN" | `UNRESOLVED` — value is relative to ULN, not absolute |

The system **never invents** `creatinine < 1.5` for "adequate renal function".

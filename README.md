# Autoformalizer

The Autoformalizer is a clinical-trial eligibility formalization engine. It bridges the gap between natural language inclusion/exclusion criteria and formal SMT-LIB constraints that can be solved deterministically by the Z3 Theorem Prover.

## Architecture

The pipeline strictly separates **understanding** (using the Gemini API) from **formalization and execution** (deterministic Python and Z3).

```
Natural Language
    ↓
Gemini Structured JSON Extraction
    ↓
AST (Abstract Syntax Tree) Construction
    ↓
Semantic Validation (Ontology Mapping, Boundary Checks)
    ↓
Deterministic SMT-LIB Generator
    ↓
Z3 Verifier
```

### Why Gemini?
Gemini is used purely as an NLP engine to perform structural and semantic extraction of text into predefined Pydantic JSON schemas. 

### Why Gemini does not directly generate SMT-LIB
Directly generating executable SMT-LIB is unsafe and prone to hallucinations, dropped negations, and semantic inversion. By generating JSON first, we can semantically validate operators, variables, and units against our controlled clinical ontology before deterministically compiling it to SMT-LIB.

## Core Components
- **Variable Ontology (`app/ontology/variables.py`)**: A strict registry of allowed variables, their bounds, types, and synonyms.
- **Normalization (`app/formalizer/normalization/mapper.py`)**: Maps extracted variables to canonical terms.
- **Logical Parsing & AST (`app/schema/ast.py`)**: Defines nested logic (AND, OR, NOT) and comparison nodes.
- **Negation Handling**: Negation is strictly preserved via `BooleanNode` (value: false) or explicit `NotNode` wrapping.
- **SMT Generator (`app/formalizer/smt/generator.py`)**: Compiles validated AST trees into `(assert ...)` statements.
- **Z3 Validation (`app/formalizer/z3/verifier.py`)**: Runs Z3 to ensure the generated logic is syntactically correct and satisfiable.
- **Error Handling**: Missing information correctly yields `UnresolvedNode` rather than fabricated constraints.
- **Caching (`app/cache/manager.py`)**: SQLite caching to avoid redundant LLM calls for identical trial strings.
- **CHIA Integration (`app/formalizer/parser/chia_adapter.py`)**: An adapter mapping structured CHIA clinical data into Autoformalizer payload requests.
- **Evaluation (`evaluation/evaluator.py`)**: A test framework benchmarking LLM extraction accuracy against gold/adversarial datasets.

## Example

**Input**:
`"Patients must be at least 18 years old and have EGFR-positive NSCLC."`

**Output AST**:
```json
{
  "type": "and",
  "conditions": [
    {
      "type": "comparison",
      "variable": "age",
      "operator": ">=",
      "value": 18
    },
    {
      "type": "comparison",
      "variable": "cancer_type",
      "operator": "==",
      "value": "NSCLC"
    },
    {
      "type": "boolean",
      "variable": "egfr_positive",
      "value": true
    }
  ]
}
```

**Output SMT-LIB**:
```smt
(declare-const age Int)
(declare-const cancer_type String)
(declare-const egfr_positive Bool)
(assert (and (>= age 18) (= cancer_type "NSCLC") (= egfr_positive true)))
```

## Running the API
```bash
export GEMINI_API_KEY="your-key"
pip install fastapi uvicorn google-genai z3-solver pydantic pytest
uvicorn app.api.main:app --reload
```

## Testing
Run the logic and adversarial tests:
```bash
pytest tests/test_logic.py -v
```

## Limitations & Future Work
- The current solver uses basic satisfiability. Full conformal reasoning loops with patient-specific values require injecting state into Z3 assertions.
- Temporal relationships (`WITHIN`, `AFTER`) are parsed into the AST but not currently mapped to complex SMT temporal logic.
- Complex unit conversions (e.g. `mg/dL` to `umol/L`) will require a dedicated unit conversion layer before semantic validation.

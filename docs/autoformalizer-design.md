# Autoformalizer Design Document

## A. Repository Structure
The existing repository was empty except for IDE configurations. 
Proposed structure:
```
app/
    api/              # FastAPI endpoints
    models/           # Shared models, AST representations
    schema/           # Pydantic schemas for LLM and internal validation
    ontology/         # Controlled variable registry
    formalizer/       # Core formalization logic
        llm/          # LLM integrations (GeminiProvider)
        normalization/# Synonym/term mapping
        parser/       # Text processing utilities
        ast/          # AST node definitions and logic
        validation/   # Semantic validator logic
        smt/          # Deterministic SMT generator
        z3/           # Z3 wrapper and validation interface
    storage/          # Database/persistence
    cache/            # Caching layer
    evaluation/       # Eval framework
tests/                # Test suite
examples/             # Examples for basic, clinical, adversarial usage
docs/                 # Architecture & design documentation
```

## B. Existing Components
None. The repository is blank.

## C. Existing Retrieval/Solver Interfaces
None. We will define clean boundaries for Retrieval (upstream) and Solver/Question Loop (downstream).

## D. Missing Autoformalizer Components
Everything is missing. We will build:
- Typed Intermediate Representation (AST)
- Clinical Variable Registry (Ontology)
- LLM Provider Interface & Gemini Implementation with Structured Output
- Semantic Validator
- Deterministic SMT-LIB Generator
- Z3 Integration
- FastAPI Backend & Caching
- CHIA Adapter

## E. Proposed Architecture
1. **Input**: Clinical Trial Text (Inclusion/Exclusion)
2. **LLM Structured Extraction (Gemini)**: Extracts semantic parts into a strict JSON representation using Pydantic schemas.
3. **AST Construction & Validation**: Converts raw JSON into a strongly typed AST. Applies semantic validation (types, boundaries, missing info).
4. **SMT Generator**: Deterministically maps the AST to SMT-LIB constraints.
5. **Z3 Verifier**: Parses and validates the generated SMT-LIB for syntactic/type correctness.
6. **Output**: A structured `FormalizationResult`.

## F. AST / Schema Design
We will use a Pydantic-based generic AST structure:
- `ComparisonNode`: variable, operator (==, !=, >, <, >=, <=), value, unit
- `BooleanNode`: variable, boolean value
- `LogicalNode`: AND / OR / NOT wrappers containing sub-nodes
- `TemporalNode`: event, relation (before, after, within), reference, amount, unit
- `UnresolvedNode`: reason for failure to formalize

## G. Variable Ontology
A controlled registry of clinical variables (e.g., `age`, `egfr_positive`, `cancer_type`). 
Each variable defines:
- Type (Int, Bool, String)
- Allowed operators
- Allowed units
- Synonyms

## H. Gemini Integration Design
We will use `google-genai` SDK with `response_schema` (structured output) to force the LLM to return data matching our AST definitions. We will use a baseline model `gemini-3.8-flash` (configurable via `GEMINI_MODEL`), focusing on source faithfulness and avoiding hallucination.

## I. Validation Design
A `SemanticValidator` will traverse the AST and verify:
- Variables exist in the Ontology.
- Operators match the variable's allowed operators.
- Values match the variable's type.
- Complex bounds (e.g., age < 18 and age > 65) are flagged.

## J. Storage/Cache Design
A caching layer keyed by `trial_id`, `source_text_hash`, `versions`. 
Initial backend: SQLite. 

## K. Test Plan
- **Gold Tests**: 50+ manually curated inputs covering all AST node types and clinical categories.
- **Adversarial Tests**: Variations with subtle negative/temporal changes to test model resilience.
- **Z3 Tests**: End-to-end tests ensuring generated SMT-LIB compiles and yields expected SAT/UNSAT results.

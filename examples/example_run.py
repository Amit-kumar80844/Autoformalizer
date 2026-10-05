import os
import sys

# Add the root directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.formalizer.pipeline import AutoformalizerPipeline

def run_example():
    print("=== Autoformalizer E2E Demo ===")
    
    # We will use a mock LLM response mechanism for demonstration if API key isn't set
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("WARNING: GEMINI_API_KEY not set. The LLM extraction will fail unless mocked.")
        print("Make sure you export GEMINI_API_KEY=your_key in your terminal.")
        
    pipeline = AutoformalizerPipeline()
    
    criterion = "Patients must be at least 18 years old and have EGFR-positive NSCLC."
    print(f"\n[Input Criterion]: {criterion}\n")
    
    result = pipeline.process(
        trial_id="NCT00012345",
        inclusion_text=criterion
    )
    
    print("[Final Result Status]:", result.status)
    print("\n[AST Structure]:")
    print(result.formal_ast.model_dump_json(indent=2) if result.formal_ast else "None")
    
    print("\n[Generated SMT-LIB]:")
    print(result.smt_lib if result.smt_lib else "None")
    
    print("\n[Extracted Required Variables]:")
    print(result.required_variables)
    
    print("\n[Warnings/Logs]:")
    for w in result.warnings:
        print(f" - {w}")

if __name__ == "__main__":
    run_example()

import json
import os
import sys
from typing import List, Dict, Any

# Add the root directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.formalizer.pipeline import AutoformalizerPipeline
from pydantic import TypeAdapter
from app.schema.ast import ASTNode

class Evaluator:
    def __init__(self, pipeline: AutoformalizerPipeline):
        self.pipeline = pipeline
        self.ast_adapter = TypeAdapter(ASTNode)

    def evaluate_dataset(self, dataset_path: str) -> Dict[str, Any]:
        with open(dataset_path, "r") as f:
            dataset = json.load(f)
            
        total = len(dataset)
        successes = 0
        failures = []
        
        def strip_metadata(d):
            if isinstance(d, dict):
                return {k: strip_metadata(v) for k, v in d.items() if k not in ("source_text", "source_span")}
            elif isinstance(d, list):
                return [strip_metadata(i) for i in d]
            return d
            
        for case in dataset:
            text = case["text"]
            expected_dict = case["expected_ast"]
            expected_ast = self.ast_adapter.validate_python(expected_dict)
            
            print(f"Evaluating: {case['id']}...")
            result = self.pipeline.process(
                trial_id=case["id"],
                criterion_text=text,
                use_cache=False # Force LLM to run for evaluation
            )
            
            # Compare without metadata
            expected_clean = strip_metadata(expected_ast.model_dump()) if expected_ast else None
            actual_clean = strip_metadata(result.formal_ast.model_dump()) if result.formal_ast else None
            
            if actual_clean and actual_clean == expected_clean:
                successes += 1
            else:
                failures.append({
                    "id": case["id"],
                    "text": text,
                    "expected": expected_clean,
                    "actual": actual_clean,
                    "warnings": result.warnings
                })
                
        accuracy = successes / total if total > 0 else 0.0
        
        return {
            "total": total,
            "successes": successes,
            "accuracy": accuracy,
            "failures": failures
        }

if __name__ == "__main__":
    pipeline = AutoformalizerPipeline()
    evaluator = Evaluator(pipeline)
    
    gold_path = os.path.join(os.path.dirname(__file__), "../tests/dataset_gold.json")
    print(f"--- Running Evaluation on {gold_path} ---")
    # This requires GEMINI_API_KEY to be set!
    if os.environ.get("GEMINI_API_KEY"):
        metrics = evaluator.evaluate_dataset(gold_path)
        print(f"Accuracy: {metrics['accuracy']:.2f}")
    else:
        print("GEMINI_API_KEY not set. Cannot run full LLM evaluation.")

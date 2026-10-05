import z3
from typing import Literal, Tuple

class Z3Verifier:
    """
    Validates and solves the SMT-LIB constraints using the Z3 solver.
    """
    
    def verify(self, smt_lib_string: str) -> Tuple[Literal["SAT", "UNSAT", "UNKNOWN", "ERROR"], str]:
        """
        Parses SMT-LIB and checks for satisfiability.
        Returns the status and a message or error detail.
        """
        if not smt_lib_string or smt_lib_string.startswith("; SMT generation aborted"):
            return "ERROR", "Invalid or aborted SMT-LIB string"
            
        solver = z3.Solver()
        try:
            # z3.parse_smt2_string parses the assertions and returns a vector of ASTs.
            assertions = z3.parse_smt2_string(smt_lib_string)
            solver.add(assertions)
            
            result = solver.check()
            if result == z3.sat:
                return "SAT", "Constraints are satisfiable."
            elif result == z3.unsat:
                return "UNSAT", "Constraints are logically unsatisfiable."
            else:
                return "UNKNOWN", "Solver could not determine satisfiability."
                
        except z3.Z3Exception as e:
            return "ERROR", f"Z3 Syntax/Type Error: {str(e)}"
        except Exception as e:
            return "ERROR", f"Unexpected error during Z3 verification: {str(e)}"

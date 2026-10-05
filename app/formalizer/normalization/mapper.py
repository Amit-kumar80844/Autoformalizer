from typing import Optional
from app.ontology.variables import registry, ClinicalVariable

class NormalizationMapper:
    @staticmethod
    def map_to_canonical(raw_variable_name: str) -> Optional[ClinicalVariable]:
        """
        Maps a raw variable name extracted by the LLM to a canonical ClinicalVariable.
        Returns None if mapping fails.
        """
        return registry.get(raw_variable_name.strip())

    @staticmethod
    def is_valid_value_for_type(value, variable: ClinicalVariable) -> bool:
        """
        Checks if the provided value matches the expected type in the ontology.
        """
        var_type = variable.type.value
        if var_type == "INTEGER":
            return isinstance(value, int)
        elif var_type == "REAL":
            return isinstance(value, (int, float))
        elif var_type == "BOOLEAN":
            return isinstance(value, bool)
        elif var_type == "STRING":
            return isinstance(value, str)
        elif var_type == "SET":
            return isinstance(value, list)
        return True # Fallback

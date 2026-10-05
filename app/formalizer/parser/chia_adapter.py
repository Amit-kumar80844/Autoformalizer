from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.api.main import FormalizationRequest

class ChiaAnnotation(BaseModel):
    id: str
    text: str
    span: List[int]
    label: str

class ChiaDocument(BaseModel):
    trial_id: str
    text: str
    annotations: List[ChiaAnnotation]
    relations: Optional[List[Dict[str, Any]]] = None

class ChiaAdapter:
    """
    Adapter to convert CHIA dataset formatting into Autoformalizer input representations.
    """
    
    @staticmethod
    def to_request(doc: ChiaDocument) -> FormalizationRequest:
        """
        In CHIA, the text contains the criteria. 
        We pass the raw text to our pipeline, but we might also use annotations 
        to pre-filter or provide hints in the future.
        """
        # A simple adaptation mapping the full text to the inclusion criterion.
        # If CHIA explicitly splits incl/excl in metadata, we would route it here.
        return FormalizationRequest(
            trial_id=doc.trial_id,
            inclusion_text=doc.text,
            exclusion_text=None
        )

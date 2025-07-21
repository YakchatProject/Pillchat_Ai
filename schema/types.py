from pydantic import BaseModel
from typing import Dict

class OCRResult(BaseModel):
    valid: bool
    text: str
    fields: Dict[str, str]

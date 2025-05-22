from typing import Optional
from pydantic import BaseModel

class KeyCheckResult(BaseModel):
    
    key: str
    is_valid: bool
    regions: list = []
    message: Optional[str] = None

class KeyCheckStatusResponse(BaseModel):
    
    status: str  
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[KeyCheckResult] = None
    progress: Optional[float] = 0
    stage: Optional[str] = None 
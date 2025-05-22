from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class KeyStatus(str, Enum):
    VALID = "valid"
    USED = "used"
    INVALID = "invalid"
    REGION_ERROR = "region_error"
    ERROR = "error"
    PENDING = "pending"

class Key(BaseModel):
    key: str
    region: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def formatted_key(self) -> str:
        
        
        cleaned_key = ''.join(c for c in self.key if c.isalnum()).upper()
        
        
        if len(cleaned_key) != 25:
            return self.key  
        
        
        formatted = '-'.join([cleaned_key[i:i+5] for i in range(0, 25, 5)])
        return formatted
    
    def is_valid_format(self) -> bool:
        
        
        cleaned_key = ''.join(c for c in self.key if c.isalnum())
        
        
        
        if len(cleaned_key) != 25:
            return False
        
        
        
        valid_chars = set("ABCDEFGHJKMNPQRTUVWXY2346789")
        return all(c.upper() in valid_chars for c in cleaned_key)

class KeyCheckResult(BaseModel):
    key: Key
    status: KeyStatus = KeyStatus.PENDING
    error_message: Optional[str] = None
    check_time: datetime = Field(default_factory=datetime.now)
    account_used: Optional[str] = None
    region_used: Optional[str] = None
    is_global: bool = False
    check_id: Optional[str] = None
    
    def mark_valid(self):
        self.status = KeyStatus.VALID
    
    def mark_used(self):
        self.status = KeyStatus.USED
    
    def mark_invalid(self):
        self.status = KeyStatus.INVALID
    
    def mark_region_error(self, message: str):
        self.status = KeyStatus.REGION_ERROR
        self.error_message = message
    
    def mark_error(self, message: str):
        self.status = KeyStatus.ERROR
        self.error_message = message

class KeyCheckBatch(BaseModel):
    keys: List[Key]
    results: List[KeyCheckResult] = []
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    progress: float = 0.0  
    
    def add_result(self, result: KeyCheckResult):
        self.results.append(result)
        self.progress = len(self.results) / len(self.keys)
        
        
        if len(self.results) == len(self.keys):
            self.completed_at = datetime.now()
    
    def get_valid_keys(self) -> List[KeyCheckResult]:
        return [result for result in self.results if result.status == KeyStatus.VALID]
    
    def get_used_keys(self) -> List[KeyCheckResult]:
        return [result for result in self.results if result.status == KeyStatus.USED]
    
    def get_invalid_keys(self) -> List[KeyCheckResult]:
        return [result for result in self.results if result.status == KeyStatus.INVALID]
    
    def get_region_error_keys(self) -> List[KeyCheckResult]:
        return [result for result in self.results if result.status == KeyStatus.REGION_ERROR]
    
    def get_error_keys(self) -> List[KeyCheckResult]:
        return [result for result in self.results if result.status == KeyStatus.ERROR] 
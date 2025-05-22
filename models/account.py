from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, EmailStr

class AccountStatus(str, Enum):
    AVAILABLE = "available"  
    IN_USE = "in_use"        
    COOLDOWN = "cooldown"    
    ERROR = "error"          
    BLOCKED = "blocked"      

class MicrosoftAccount(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    email: EmailStr
    password: str  
    status: AccountStatus = AccountStatus.AVAILABLE
    checks_count: int = 0  
    last_check_time: Optional[datetime] = None
    last_used_at: Optional[datetime] = None  
    cooldown_until: Optional[datetime] = None  
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True  
    
    def can_check_keys(self, max_checks: int = 10) -> bool:
        
        
        if not self.is_active or self.status in [AccountStatus.ERROR, AccountStatus.BLOCKED]:
            return False
        
        
        if self.status == AccountStatus.COOLDOWN and self.cooldown_until:
            if datetime.now() >= self.cooldown_until:
                
                self.status = AccountStatus.AVAILABLE
                self.cooldown_until = None
            else:
                
                return False
        
        
        if self.status == AccountStatus.IN_USE:
            return False
        
        
        return self.checks_count < max_checks
    
    def mark_in_use(self):
        
        self.status = AccountStatus.IN_USE
        self.last_used_at = datetime.now()
    
    def mark_available(self):
        
        self.status = AccountStatus.AVAILABLE
    
    def mark_cooldown(self, cooldown_period: int = 3600):
        
        self.status = AccountStatus.COOLDOWN
        self.cooldown_until = datetime.now().replace(microsecond=0) + datetime.timedelta(seconds=cooldown_period)
    
    def mark_error(self, message: str):
        
        self.status = AccountStatus.ERROR
        self.error_message = message
    
    def mark_blocked(self, message: str = "Account blocked by Microsoft"):
        
        self.status = AccountStatus.BLOCKED
        self.error_message = message
    
    def register_key_check(self):
        
        self.checks_count += 1
        self.last_check_time = datetime.now()
        self.last_used_at = datetime.now()

class AccountPool(BaseModel):
    accounts: List[MicrosoftAccount] = []
    current_index: int = 0
    
    def add_account(self, account: MicrosoftAccount):
        
        self.accounts.append(account)
    
    def remove_account(self, account_id: str):
        
        self.accounts = [acc for acc in self.accounts if acc.id != account_id]
    
    def get_available_account(self, max_checks: int = 10) -> Optional[MicrosoftAccount]:
        
        if not self.accounts:
            return None
        
        
        start_index = self.current_index
        while True:
            account = self.accounts[self.current_index]
            
            
            self.current_index = (self.current_index + 1) % len(self.accounts)
            
            
            if account.can_check_keys(max_checks):
                return account
            
            
            
            if self.current_index == start_index:
                return None
    
    def get_statistics(self) -> Dict:
        
        total = len(self.accounts)
        available = sum(1 for acc in self.accounts if acc.status == AccountStatus.AVAILABLE)
        in_use = sum(1 for acc in self.accounts if acc.status == AccountStatus.IN_USE)
        cooldown = sum(1 for acc in self.accounts if acc.status == AccountStatus.COOLDOWN)
        error = sum(1 for acc in self.accounts if acc.status == AccountStatus.ERROR)
        blocked = sum(1 for acc in self.accounts if acc.status == AccountStatus.BLOCKED)
        total_checks = sum(acc.checks_count for acc in self.accounts)
        
        return {
            "total": total,
            "available": available,
            "in_use": in_use,
            "cooldown": cooldown,
            "error": error,
            "blocked": blocked,
            "total_checks": total_checks
        } 
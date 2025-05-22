from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from models.account import MicrosoftAccount, AccountStatus
from services.account_manager import AccountManager

router = APIRouter()

class AccountCreate(BaseModel):
    email: EmailStr
    password: str

class AccountResponse(BaseModel):
    id: str
    email: EmailStr
    status: AccountStatus
    checks_count: int
    cooldown_until: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None

class AccountStatistics(BaseModel):
    total_accounts: int
    available_accounts: int
    in_use_accounts: int
    cooldown_accounts: int
    error_accounts: int
    blocked_accounts: int
    total_checks: int

async def get_account_manager():
    account_manager = AccountManager()
    await account_manager.initialize()
    return account_manager

@router.get("/", response_model=List[AccountResponse])
async def get_accounts(
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    accounts = account_manager.account_pool.accounts
    
    
    return [
        {
            "id": account.id,
            "email": account.email,
            "status": account.status,
            "checks_count": account.checks_count,
            "cooldown_until": account.cooldown_until,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
        }
        for account in accounts
    ]

@router.post("/", response_model=AccountResponse)
async def create_account(
    account_data: AccountCreate,
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    account = await account_manager.add_account(
        email=account_data.email,
        password=account_data.password
    )
    
    return {
        "id": account.id,
        "email": account.email,
        "status": account.status,
        "checks_count": account.checks_count,
        "cooldown_until": account.cooldown_until,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
    }

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    account = await account_manager.get_account(account_id)
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with ID {account_id} not found")
    
    return {
        "id": account.id,
        "email": account.email,
        "status": account.status,
        "checks_count": account.checks_count,
        "cooldown_until": account.cooldown_until,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
    }

@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    success = await account_manager.remove_account(account_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Account with ID {account_id} not found")
    
    return {"message": f"Account with ID {account_id} deleted"}

@router.post("/{account_id}/reset")
async def reset_account_checks(
    account_id: str,
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    success = await account_manager.reset_account_checks(account_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Account with ID {account_id} not found")
    
    return {"message": f"Account with ID {account_id} checks reset"}

@router.post("/reset-all")
async def reset_all_accounts(
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    await account_manager.reset_all_accounts()
    return {"message": "All accounts checks reset"}

@router.get("/statistics", response_model=AccountStatistics)
async def get_accounts_statistics(
    account_manager: AccountManager = Depends(get_account_manager)
):
    
    stats = await account_manager.get_accounts_stats()
    
    return {
        "total_accounts": stats["total"],
        "available_accounts": stats["available"],
        "in_use_accounts": stats["in_use"],
        "cooldown_accounts": stats["cooldown"],
        "error_accounts": stats["error"],
        "blocked_accounts": stats["blocked"],
        "total_checks": stats["total_checks"]
    } 
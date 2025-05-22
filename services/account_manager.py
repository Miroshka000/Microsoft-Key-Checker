import asyncio
import json
import logging
import os
import random
from datetime import datetime
from typing import List, Optional, Dict

from models.account import MicrosoftAccount, AccountPool, AccountStatus
from utils.crypto import encrypt_data, decrypt_data
from config import config, DATA_DIR

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class AccountManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.account_pool = AccountPool()
        self.accounts_file = os.path.join(DATA_DIR, "accounts.json")
        self.lock = asyncio.Lock()
    
    async def initialize(self):
        
        await self.load_accounts()
        self.logger.info(f"Initialized AccountManager with {len(self.account_pool.accounts)} accounts")
    
    async def add_account(self, email: str, password: str) -> MicrosoftAccount:
        
        async with self.lock:
            
            for account in self.account_pool.accounts:
                if account.email == email:
                    self.logger.warning(f"Account with email {email} already exists")
                    return account
            
            
            account = MicrosoftAccount(
                email=email,
                password=password,
                status=AccountStatus.AVAILABLE,
                created_at=datetime.now()
            )
            
            self.account_pool.add_account(account)
            self.logger.info(f"Added new account: {email}")
            
            
            await self.save_accounts()
            
            return account
    
    async def remove_account(self, account_id: str) -> bool:
        
        async with self.lock:
            initial_count = len(self.account_pool.accounts)
            self.account_pool.remove_account(account_id)
            
            if len(self.account_pool.accounts) < initial_count:
                self.logger.info(f"Removed account with ID: {account_id}")
                await self.save_accounts()
                return True
            else:
                self.logger.warning(f"Account with ID {account_id} not found")
                return False
    
    async def get_account(self, account_id: str) -> Optional[MicrosoftAccount]:
        
        for account in self.account_pool.accounts:
            if account.id == account_id:
                return account
        return None
    
    async def get_available_account(self) -> Optional[MicrosoftAccount]:
        
        async with self.lock:
            account = self.account_pool.get_available_account(
                max_checks=config.microsoft_account.max_checks_per_account
            )
            
            if account:
                account.mark_in_use()
                self.logger.info(f"Selected account for use: {account.email}")
                await self.save_accounts()
            else:
                self.logger.warning("No available accounts found")
            
            return account
    
    async def release_account(self, account: MicrosoftAccount, use_cooldown: bool = True):
        
        async with self.lock:
            
            account.register_key_check()
            
            
            if account.checks_count >= config.microsoft_account.max_checks_per_account and use_cooldown:
                account.mark_cooldown(cooldown_period=config.microsoft_account.cooldown_period)
                self.logger.info(f"Account {account.email} reached check limit, set to cooldown")
            else:
                account.mark_available()
                self.logger.info(f"Released account: {account.email}")
            
            await self.save_accounts()
    
    async def reset_account_checks(self, account_id: str) -> bool:
        
        async with self.lock:
            account = await self.get_account(account_id)
            if not account:
                return False
            
            account.checks_count = 0
            account.status = AccountStatus.AVAILABLE
            account.cooldown_until = None
            self.logger.info(f"Reset checks for account: {account.email}")
            
            await self.save_accounts()
            return True
    
    async def reset_all_accounts(self):
        
        async with self.lock:
            for account in self.account_pool.accounts:
                account.checks_count = 0
                account.status = AccountStatus.AVAILABLE
                account.cooldown_until = None
            
            self.logger.info("Reset checks for all accounts")
            await self.save_accounts()
    
    async def get_accounts_stats(self) -> Dict:
        
        return self.account_pool.get_statistics()
    
    async def load_accounts(self):
        
        try:
            if not os.path.exists(self.accounts_file):
                self.logger.info("Accounts file not found, starting with empty pool")
                return
            
            with open(self.accounts_file, "r") as f:
                encrypted_data = f.read()
            
            
            decrypted_data = decrypt_data(
                encrypted_data,
                config.security.encryption_key
            )
            
            accounts_data = json.loads(decrypted_data)
            
            
            pool = AccountPool()
            
            for account_data in accounts_data:
                account = MicrosoftAccount(**account_data)
                
                
                if account.status == AccountStatus.COOLDOWN and account.cooldown_until:
                    cooldown_until = datetime.fromisoformat(account.cooldown_until)
                    
                    
                    if datetime.now() >= cooldown_until:
                        account.status = AccountStatus.AVAILABLE
                        account.cooldown_until = None
                
                pool.add_account(account)
            
            self.account_pool = pool
            self.logger.info(f"Loaded {len(self.account_pool.accounts)} accounts from file")
        
        except Exception as e:
            self.logger.error(f"Error loading accounts: {str(e)}")
            
            self.account_pool = AccountPool()
    
    async def save_accounts(self):
        
        try:
            
            accounts_data = [account.dict() for account in self.account_pool.accounts]
            
            
            json_data = json.dumps(accounts_data, cls=DateTimeEncoder)
            
            
            encrypted_data = encrypt_data(
                json_data,
                config.security.encryption_key
            )
            
            
            os.makedirs(os.path.dirname(self.accounts_file), exist_ok=True)
            with open(self.accounts_file, "w") as f:
                f.write(encrypted_data)
            
            self.logger.debug(f"Saved {len(self.account_pool.accounts)} accounts to file")
        
        except Exception as e:
            self.logger.error(f"Error saving accounts: {str(e)}")
            raise 
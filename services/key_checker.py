import asyncio
import logging
import time
import random
from typing import List, Dict, Optional, Tuple, Any

from playwright.async_api import Page, TimeoutError

from models.key import Key, KeyCheckResult, KeyStatus, KeyCheckBatch
from models.account import MicrosoftAccount
from models.vpn import VPNRegion

from services.microsoft_auth import MicrosoftAuthenticator
from services.account_manager import AccountManager
from services.vpn_manager import VPNManager

from config import config

class KeyChecker:
    def __init__(
        self,
        account_manager: AccountManager,
        vpn_manager: VPNManager
    ):
        self.logger = logging.getLogger(__name__)
        self.account_manager = account_manager
        self.vpn_manager = vpn_manager
        self.authenticator = MicrosoftAuthenticator()
        self.running_tasks = {}  
        self.batch_results = {}  
        self.key_check_statuses = {}  
        self.key_check_stages = {
            "init": "Инициализация проверки",
            "vpn_connect": "Подключение к VPN",
            "browser_init": "Инициализация браузера",
            "login": "Вход в аккаунт Microsoft",
            "navigate": "Переход на страницу проверки ключей",
            "key_input": "Ввод ключа для проверки",
            "check_processing": "Обработка результатов проверки",
            "cleanup": "Завершение проверки",
            "completed": "Проверка завершена"
        }
    
    async def initialize(self):
        
        
        self.logger.info("Initialized KeyChecker")
    
    async def close(self):
        
        await self.authenticator.close()
        self.logger.info("Closed KeyChecker resources")
    
    def generate_check_id(self, key: Key) -> str:
        
        
        clean_key = key.formatted_key.replace('-', '').upper()
        
        
        timestamp = int(time.time())
        
        
        random_part = str(random.randint(1000, 9999))
        
        
        check_id = f"check_{clean_key}_{timestamp}_{random_part}"
        
        self.logger.info(f"Сгенерирован ID проверки: {check_id}")
        return check_id
    
    def update_key_status(self, check_id: str, stage: str, progress: int, message: str = None, is_error: bool = False, result: Dict = None):
        
        
        normalized_check_id = check_id
        if check_id.startswith("temp_check_"):
            
            key_part = check_id.split("temp_check_")[1].split("_")[0]
            normalized_check_id = f"check_{key_part}_{int(time.time())}"
            self.logger.info(f"Нормализация ID: {check_id} -> {normalized_check_id}")
        
        
        if check_id != normalized_check_id:
            self.key_check_statuses[check_id] = {}
            self.key_check_statuses[check_id]["alias_for"] = normalized_check_id
        
        
        if normalized_check_id not in self.key_check_statuses:
            self.key_check_statuses[normalized_check_id] = {}
        
        status = self.key_check_statuses[normalized_check_id]
        status["stage"] = stage
        status["progress"] = progress
        status["message"] = message or self.key_check_stages.get(stage, stage)
        status["last_update"] = time.time()
        status["status"] = "error" if is_error else "completed" if result else "in_progress"
        
        if is_error:
            status["error"] = True
            status["error_message"] = message
        
        if result:
            status["result"] = result
            status["completed"] = True
        
        
        current_time = time.time()
        for id_to_check in list(self.key_check_statuses.keys()):
            if current_time - self.key_check_statuses[id_to_check].get("last_update", 0) > 3600:
                
                if "alias_for" not in self.key_check_statuses[id_to_check]:
                    del self.key_check_statuses[id_to_check]
    
    async def get_key_status(self, check_id: str) -> Dict[str, Any]:
        
        self.logger.info(f"Запрос статуса для ID: {check_id}")
        
        
        if check_id in self.key_check_statuses:
            
            if "alias_for" in self.key_check_statuses[check_id]:
                actual_id = self.key_check_statuses[check_id]["alias_for"]
                self.logger.info(f"ID {check_id} является алиасом для {actual_id}")
                return await self.get_key_status(actual_id)
            
            
            status = self.key_check_statuses[check_id]
            return {
                "status": status.get("status", "in_progress"),
                "stage": status.get("stage", "unknown"),
                "progress": status.get("progress", 0),
                "message": status.get("message", ""),
                "error_message": status.get("error_message", "") if status.get("error", False) else None,
                "result": status.get("result", None)
            }
        
        
        key_part = None
        timestamp_part = None
        
        
        if check_id.startswith("check_"):
            parts = check_id.split("_", 2)
            if len(parts) >= 3:
                key_part = parts[1]
                timestamp_part = parts[2]
        elif check_id.startswith("temp_check_"):
            parts = check_id.split("temp_check_", 1)[1].split("_")
            if len(parts) >= 2:
                key_part = parts[0]
                timestamp_part = parts[1]
        
        if key_part:
            
            for id_to_check, status in self.key_check_statuses.items():
                if "alias_for" not in status and id_to_check.startswith(f"check_{key_part}"):
                    self.logger.info(f"Найден похожий ID: {id_to_check} для запроса {check_id}")
                    
                    self.key_check_statuses[check_id] = {"alias_for": id_to_check}
                    return await self.get_key_status(id_to_check)
        
        
        self.logger.info(f"Статус не найден для ID: {check_id}")
        return {
            "status": "not_found",
            "message": "Проверка не найдена"
        }
    
    def _process_logger_marker(self, check_id: str, logger_message: str):
        
        if "KEY_CHECK_MARKER:" not in logger_message:
            return False
        
        try:
            
            parts = logger_message.split("KEY_CHECK_MARKER:", 1)[1].strip()
            stage_info = parts.split(":", 2)
            
            if len(stage_info) >= 3:
                stage = stage_info[0]
                progress = int(stage_info[1])
                message = stage_info[2]
                
                
                self.update_key_status(check_id, stage, progress, message)
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке маркера: {str(e)}")
        
        return False
    
    async def check_key(self, key: Key, account: Optional[MicrosoftAccount] = None, region: Optional[str] = None) -> KeyCheckResult:
        
        
        result = KeyCheckResult(key=key)
        
        
        check_id = self.generate_check_id(key)
        result.check_id = check_id
        
        
        temp_check_id = f"temp_check_{key.formatted_key.replace('-', '')}_{int(time.time())}"
        
        
        self.update_key_status(check_id, "init", 5, "Инициализация проверки")
        self.update_key_status(temp_check_id, "init", 5, "Инициализация проверки")
        
        self.logger.info(f"Начинаем проверку ключа: {key.formatted_key}, ID проверки: {check_id}, временный ID: {temp_check_id}")
        
        
        auth = MicrosoftAuthenticator()
        
        try:
            
            if not region and key.region:
                region = key.region
            
            
            if region and config.vpn.enabled:
                self.update_key_status(check_id, "vpn_connect", 10, "Подключение к VPN")
                vpn_service = config.vpn.default_provider
                self.logger.info(f"Connecting to VPN region: {region}")
                vpn_connected = await self.vpn_manager.connect(vpn_service, region)
                if not vpn_connected:
                    error_msg = f"Failed to connect to VPN region: {region}"
                    result.mark_error(error_msg)
                    self.update_key_status(check_id, "vpn_connect", 15, error_msg, True)
                    return result
                
                result.region_used = region
            
            
            account_from_pool = False
            if not account:
                account = await self.account_manager.get_available_account()
                if not account:
                    error_msg = "No available accounts"
                    result.mark_error(error_msg)
                    self.update_key_status(check_id, "init", 10, error_msg, True)
                    return result
                account_from_pool = True
            
            result.account_used = account.email
            
            
            self.update_key_status(check_id, "browser_init", 20, "Инициализация браузера")
            if not await auth.initialize():
                error_msg = "Failed to initialize browser"
                result.mark_error(error_msg)
                self.update_key_status(check_id, "browser_init", 25, error_msg, True)
                return result
            
            
            original_info = auth.logger.info
            original_error = auth.logger.error
            
            
            def log_info_with_markers(message, *args, **kwargs):
                original_info(message, *args, **kwargs)
                self._process_logger_marker(check_id, message)
            
            def log_error_with_markers(message, *args, **kwargs):
                original_error(message, *args, **kwargs)
                if "KEY_CHECK_MARKER:" in message:
                    self._process_logger_marker(check_id, message)
            
            
            auth.logger.info = log_info_with_markers
            auth.logger.error = log_error_with_markers
            
            
            self.update_key_status(check_id, "login", 30, "Вход в аккаунт Microsoft")
            login_success = await auth.login(account)
            if not login_success:
                error_msg = "Failed to login to Microsoft account"
                result.mark_error(error_msg)
                self.update_key_status(check_id, "login", 35, error_msg, True)
                return result
            
            
            self.update_key_status(check_id, "navigate", 50, "Переход на страницу проверки ключей")
            if not await auth.navigate_to_redeem_page():
                error_msg = "Failed to navigate to redeem page"
                result.mark_error(error_msg)
                self.update_key_status(check_id, "navigate", 55, error_msg, True)
                return result
            
            
            self.update_key_status(check_id, "key_input", 70, "Ввод и проверка ключа")
            
            
            check_result = await auth.check_key(key.formatted_key)
            
            
            self.update_key_status(check_id, "check_processing", 90, "Анализ результатов проверки")
            self.logger.info(f"Key check result: {check_result}")
            
            if check_result['status'] == 'success':
                result.mark_valid()
            elif check_result['status'] == 'used':
                result.mark_used()
            elif check_result['status'] == 'invalid':
                result.mark_invalid()
            elif check_result['status'] == 'region_error' or check_result['status'] == 'disabled':
                result.mark_region_error(check_result['message'])
            elif check_result['status'] == 'unknown':
                
                result.mark_error(f"Unknown key status: {check_result['message']}")
            else:
                result.mark_error(check_result['message'])
            
            
            self.update_key_status(check_id, "cleanup", 95, "Завершение проверки")
            await auth.logout()
            await auth.close()
            
            
            if account_from_pool:
                await self.account_manager.release_account(account)
            
            
            if region and config.vpn.enabled:
                await self.vpn_manager.disconnect()
            
            
            self.logger.info(f"Key check completed: {key.formatted_key}, Status: {result.status}")
            
            
            final_result = {
                "key": result.key.formatted_key,
                "status": result.status,
                "error_message": result.error_message,
                "region_used": result.region_used,
                "is_global": result.is_global,
                "message": check_result.get('message', None)
            }
            self.update_key_status(check_id, "completed", 100, "Проверка завершена успешно", False, final_result)
            
            
            temp_check_id = f"temp_check_{key.formatted_key.replace('-', '')}_{int(time.time())}"
            self.update_key_status(temp_check_id, "completed", 100, "Проверка завершена успешно", False, final_result)
            
            self.logger.info(f"Key check completed and saved with IDs: {check_id}, {temp_check_id}")
            
            return result
        
        except Exception as e:
            
            error_msg = f"Ошибка при проверке ключа: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            
            result.mark_error(error_msg)
            
            
            self.update_key_status(check_id, "error", 100, error_msg, True)
            temp_check_id = f"temp_check_{key.formatted_key.replace('-', '')}_{int(time.time())}"
            self.update_key_status(temp_check_id, "error", 100, error_msg, True)
            
            self.logger.info(f"Key check failed and error saved with IDs: {check_id}, {temp_check_id}")
            
            
            try:
                
                if auth:
                    await auth.close()
                
                
                if account_from_pool and account:
                    await self.account_manager.release_account(account)
                
                
                if region and config.vpn.enabled:
                    await self.vpn_manager.disconnect()
            except Exception as cleanup_error:
                
                self.logger.error(f"Ошибка при освобождении ресурсов: {str(cleanup_error)}")
            
            return result
    
    async def check_keys_batch(self, keys: List[Key], regions: Optional[List[str]] = None, batch_id: Optional[str] = None) -> str:
        
        if not batch_id:
            batch_id = f"batch_{int(time.time())}"
        
        batch = KeyCheckBatch(keys=keys)
        self.batch_results[batch_id] = batch
        
        
        task = asyncio.create_task(self._process_batch(batch_id, keys, regions))
        self.running_tasks[batch_id] = task
        
        self.logger.info(f"Started batch check with ID: {batch_id}, Keys: {len(keys)}")
        return batch_id
    
    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        
        if batch_id not in self.batch_results:
            return {
                "status": "not_found",
                "progress": 0,
                "results": []
            }
        
        batch = self.batch_results[batch_id]
        
        return {
            "status": "completed" if batch.completed_at else "in_progress",
            "progress": batch.progress,
            "total_keys": len(batch.keys),
            "processed_keys": len(batch.results),
            "valid_keys": len(batch.get_valid_keys()),
            "used_keys": len(batch.get_used_keys()),
            "invalid_keys": len(batch.get_invalid_keys()),
            "region_error_keys": len(batch.get_region_error_keys()),
            "error_keys": len(batch.get_error_keys()),
            "results": [result.dict() for result in batch.results]
        }
    
    async def get_batch_results(self, batch_id: str) -> List[KeyCheckResult]:
        
        if batch_id not in self.batch_results:
            return []
        
        batch = self.batch_results[batch_id]
        return batch.results
    
    async def _check_key_on_page(self, page: Page, key: Key) -> Tuple[str, Optional[str]]:
        
        try:
            
            await page.fill('input[aria-label="Enter code"]', "")
            
            
            await page.fill('input[aria-label="Enter code"]', key.formatted_key)
            
            
            await page.click('button:has-text("Check")')
            
            
            try:
                
                error_selector = 'div[role="alert"]'
                has_error = await page.wait_for_selector(error_selector, timeout=5000, state="attached")
                
                if has_error:
                    error_text = await has_error.text_content()
                    
                    
                    if "already been redeemed" in error_text or "already used" in error_text:
                        return "used", "Key has already been redeemed"
                    elif "invalid" in error_text.lower() or "not recognized" in error_text.lower():
                        return "invalid", "Invalid key format or not recognized"
                    elif "region" in error_text.lower() or "country" in error_text.lower():
                        return "region_error", error_text
                    else:
                        return "error", error_text
            
            except TimeoutError:
                
                success_selector = "h1:has-text('You're')"
                try:
                    has_success = await page.wait_for_selector(success_selector, timeout=5000, state="attached")
                    if has_success:
                        
                        return "valid", None
                except TimeoutError:
                    
                    return "error", "Failed to determine key status"
            
            
            await page.goto(config.redeem_url)
            await page.wait_for_selector('input[aria-label="Enter code"]', timeout=config.browser.timeout)
            
            return "error", "Unknown error during key check"
        
        except Exception as e:
            return "error", f"Error checking key: {str(e)}"
    
    async def _process_batch(self, batch_id: str, keys: List[Key], regions: Optional[List[str]] = None):
        
        try:
            batch = self.batch_results[batch_id]
            
            
            semaphore = asyncio.Semaphore(config.key.parallel_checks)
            
            
            tasks = []
            
            for i, key in enumerate(keys):
                region = None
                if regions and i < len(regions):
                    region = regions[i]
                
                
                tasks.append(self._check_key_with_semaphore(semaphore, key, batch, region))
            
            
            await asyncio.gather(*tasks)
            
            
            batch.completed_at = time.time()
            
            self.logger.info(f"Batch check completed: {batch_id}, Keys: {len(keys)}")
        
        except Exception as e:
            self.logger.error(f"Error processing batch {batch_id}: {str(e)}")
        
        finally:
            
            if batch_id in self.running_tasks:
                del self.running_tasks[batch_id]
    
    async def _check_key_with_semaphore(self, semaphore: asyncio.Semaphore, key: Key, batch: KeyCheckBatch, region: Optional[str] = None):
        
        async with semaphore:
            
            account = await self.account_manager.get_available_account()
            
            if not account:
                result = KeyCheckResult(key=key)
                result.mark_error("No available accounts")
                batch.add_result(result)
                return
            
            try:
                
                result = await self.check_key(key, account, region)
                
                
                batch.add_result(result)
                
                
                await self.account_manager.release_account(account)
                
                
                await asyncio.sleep(config.key.check_delay)
            
            except Exception as e:
                self.logger.error(f"Error checking key {key.formatted_key}: {str(e)}")
                
                
                await self.account_manager.release_account(account)
                
                
                result = KeyCheckResult(key=key)
                result.mark_error(f"Error checking key: {str(e)}")
                batch.add_result(result) 
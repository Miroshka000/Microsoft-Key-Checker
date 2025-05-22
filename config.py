import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

class KeyConfig(BaseModel):
    max_keys_per_check: int = 1000
    parallel_checks: int = 5
    check_delay: float = 1.0

class MicrosoftAccountConfig(BaseModel):
    max_checks_per_account: int = 10
    cooldown_period: int = 3600  
    login_timeout: int = 60  
    account_rotation_strategy: str = "sequential"  

class VPNConfig(BaseModel):
    enabled: bool = True
    providers: List[str] = ["NordVPN", "Surfshark", "Custom"]
    default_provider: str = "Custom"
    connection_timeout: int = 30  
    retry_attempts: int = 3

class BrowserConfig(BaseModel):
    browser_type: str = "chromium"  
    headless: bool = True
    user_agent: Optional[str] = None
    viewport_size: Dict[str, int] = {"width": 1920, "height": 1080}
    timeout: int = 30000  

class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    workers: int = 4
    secret_key: str = "ваш-секретный-ключ-здесь"
    token_expire_minutes: int = 1440  
    cors_origins: List[str] = ["*"]  
    reload: bool = False

class SecurityConfig(BaseModel):
    encryption_key: str = "ключ-шифрования-должен-быть-в-переменных-окружения"
    hash_algorithm: str = "sha256"
    salt_length: int = 32

class Config(BaseModel):
    app_name: str = "Microsoft Key Checker"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    key: KeyConfig = KeyConfig()
    microsoft_account: MicrosoftAccountConfig = MicrosoftAccountConfig()
    vpn: VPNConfig = VPNConfig()
    browser: BrowserConfig = BrowserConfig()
    api: APIConfig = APIConfig()
    security: SecurityConfig = SecurityConfig()
    redeem_url: str = "https://account.microsoft.com/billing/redeem"

config = Config()

if os.getenv("KEY_MAX_PER_CHECK"):
    config.key.max_keys_per_check = int(os.getenv("KEY_MAX_PER_CHECK"))

if os.getenv("KEY_PARALLEL_CHECKS"):
    config.key.parallel_checks = int(os.getenv("KEY_PARALLEL_CHECKS"))

if os.getenv("MS_MAX_CHECKS_PER_ACCOUNT"):
    config.microsoft_account.max_checks_per_account = int(os.getenv("MS_MAX_CHECKS_PER_ACCOUNT"))

if os.getenv("VPN_ENABLED"):
    config.vpn.enabled = os.getenv("VPN_ENABLED").lower() == "true"

if os.getenv("BROWSER_HEADLESS"):
    config.browser.headless = os.getenv("BROWSER_HEADLESS").lower() == "true"

if os.getenv("API_SECRET_KEY"):
    config.api.secret_key = os.getenv("API_SECRET_KEY")

if os.getenv("SECURITY_ENCRYPTION_KEY"):
    config.security.encryption_key = os.getenv("SECURITY_ENCRYPTION_KEY") 
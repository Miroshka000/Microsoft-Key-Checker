import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, List

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError, Response

from config import config

logger = logging.getLogger(__name__)

async def setup_browser(
    browser_type: str = None,
    headless: bool = None,
    user_agent: str = None,
    viewport_size: Dict[str, int] = None,
    timeout: int = None
) -> Tuple[Browser, BrowserContext]:
    
    
    browser_type = browser_type or config.browser.browser_type
    headless = headless if headless is not None else config.browser.headless
    user_agent = user_agent or config.browser.user_agent
    viewport_size = viewport_size or config.browser.viewport_size
    timeout = timeout or config.browser.timeout
    
    try:
        
        playwright = await async_playwright().start()
        
        
        browser_launcher = getattr(playwright, browser_type)
        
        
        browser = await browser_launcher.launch(headless=headless)
        
        
        context_options = {"viewport": viewport_size}
        
        if user_agent:
            context_options["user_agent"] = user_agent
        
        context = await browser.new_context(**context_options)
        
        
        context.set_default_timeout(timeout)
        
        
        context.on("console", lambda msg: logger.debug(f"Console {msg.type}: {msg.text}"))
        
        return browser, context
    
    except Exception as e:
        logger.error(f"Error setting up browser: {str(e)}")
        raise

async def wait_for_navigation(page: Page, url_pattern: str, timeout: int = None) -> bool:
    
    timeout = timeout or config.browser.timeout
    
    try:
        await page.wait_for_url(url_pattern, timeout=timeout)
        return True
    
    except TimeoutError:
        logger.error(f"Navigation timeout: waited {timeout}ms for url matching {url_pattern}")
        return False
    
    except Exception as e:
        logger.error(f"Error during navigation: {str(e)}")
        return False

async def wait_for_selector(page: Page, selector: str, timeout: int = None, state: str = "visible") -> Optional[Any]:
    
    timeout = timeout or config.browser.timeout
    
    try:
        element = await page.wait_for_selector(selector, timeout=timeout, state=state)
        return element
    
    except TimeoutError:
        logger.error(f"Selector timeout: waited {timeout}ms for selector {selector}")
        return None
    
    except Exception as e:
        logger.error(f"Error waiting for selector: {str(e)}")
        return None

async def wait_for_network_idle(page: Page, timeout: int = None) -> bool:
    
    timeout = timeout or config.browser.timeout
    
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    
    except TimeoutError:
        logger.error(f"Network idle timeout: waited {timeout}ms")
        return False
    
    except Exception as e:
        logger.error(f"Error waiting for network idle: {str(e)}")
        return False

async def wait_for_response(page: Page, url_pattern: str, timeout: int = None) -> Optional[Response]:
    
    timeout = timeout or config.browser.timeout
    
    try:
        response = await page.wait_for_response(url_pattern, timeout=timeout)
        return response
    
    except TimeoutError:
        logger.error(f"Response timeout: waited {timeout}ms for response matching {url_pattern}")
        return None
    
    except Exception as e:
        logger.error(f"Error waiting for response: {str(e)}")
        return None

async def take_screenshot(page: Page, file_path: str) -> bool:
    
    try:
        await page.screenshot(path=file_path)
        logger.info(f"Screenshot saved to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error taking screenshot: {str(e)}")
        return False

async def fill_form(page: Page, form_data: Dict[str, str]) -> bool:
    
    try:
        for selector, value in form_data.items():
            await page.fill(selector, value)
        
        return True
    
    except Exception as e:
        logger.error(f"Error filling form: {str(e)}")
        return False

async def click_element(page: Page, selector: str, timeout: int = None, wait_for_navigation: bool = False) -> bool:
    
    timeout = timeout or config.browser.timeout
    
    try:
        
        await page.wait_for_selector(selector, timeout=timeout, state="visible")
        
        if wait_for_navigation:
            
            async with page.expect_navigation(timeout=timeout):
                await page.click(selector)
        else:
            
            await page.click(selector)
        
        return True
    
    except TimeoutError:
        logger.error(f"Click timeout: waited {timeout}ms for selector {selector}")
        return False
    
    except Exception as e:
        logger.error(f"Error clicking element: {str(e)}")
        return False 
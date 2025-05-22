import asyncio
import logging
import time
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError

from models.account import MicrosoftAccount, AccountStatus
from config import config


class MicrosoftAuthenticator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_account: Optional[MicrosoftAccount] = None
    
    async def initialize(self):
        try:
            playwright = await async_playwright().start()
            browser_type = getattr(playwright, config.browser.browser_type)

            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--dns-server=8.8.8.8,8.8.4.4'
            ]
            
            self.browser = await browser_type.launch(
                headless=config.browser.headless,
                args=browser_args,
                timeout=60000
            )

            context_options = {
                "viewport": config.browser.viewport_size,
                "ignore_https_errors": True
            }

            if not config.browser.user_agent:
                context_options["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            else:
                context_options["user_agent"] = config.browser.user_agent
            
            self.context = await self.browser.new_context(**context_options)

            self.context.on("console", lambda msg: self.logger.info(f"Console {msg.type}: {msg.text}"))

            self.context.on("page", lambda page: page.on("navigate", 
                            lambda url: self.logger.info(f"Navigation: {url}")))
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {str(e)}")
            return False
    
    async def close(self):
        try:
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            self.context = None
            self.browser = None
            self.page = None
            self.current_account = None
        except Exception as e:
            self.logger.error(f"Error closing browser: {str(e)}")
    
    async def handle_alternative_login_flows(self) -> bool:
        try:
            selectors = {
                "stay_signed_in": 'input[id="KmsiCheckboxField"]',
                "stay_signed_in_button": 'input[id="idSIButton9"]',
                "security_code": 'input[name="otc"]',
                "security_code_submit": 'input[type="submit"]',
                "verification_method": '[role="button"]',
                "skip_button": 'input[value="Skip"]',
                "not_now_button": 'a:has-text("Not now")',
                "next_button": 'input[value="Next"]',
            }

            for _ in range(5):
                current_url = self.page.url
                self.logger.info(f"Processing alternative flow. Current URL: {current_url}")

                if "https://account.microsoft.com" in current_url:
                    self.logger.info("Successfully reached account page")
                    return True

                if "login.live.com/ppsecure/post.srf" in current_url:
                    self.logger.info("Detected post.srf intermediate page - this often contains dialogs")

                    post_srf_handled = await self.handle_post_srf_page()
                    if post_srf_handled:
                        self.logger.info("Post.srf page successfully handled by specialized handler")
                        current_url = self.page.url
                        if "account.microsoft.com" in current_url:
                            self.logger.info("Successfully reached account page after post.srf handling")
                            return True

                    try:
                        await self.page.screenshot(path="post_srf_page.png")
                    except:
                        pass

                    yes_button_selectors = [
                        'input[id="idSIButton9"]',
                        'button[data-testid="primaryButton"]',
                        'button:has-text("Да")',
                        'button:has-text("Yes")'
                    ]
                    
                    no_button_selectors = [
                        'button[data-testid="secondaryButton"]',
                        'button:has-text("Нет")',
                        'button:has-text("No")',
                        'input[value="Нет"]',
                        'input[value="No"]'
                    ]

                    stay_signed_question = await self.page.query_selector('div:has-text("Не выходить из системы?")')
                    if stay_signed_question:
                        self.logger.info("Found 'Stay signed in' question on post.srf page")

                        for selector in no_button_selectors:
                            no_button = await self.page.query_selector(selector)
                            if no_button:
                                try:
                                    await no_button.click(force=True)
                                    self.logger.info(f"Clicked 'No' button with selector: {selector}")
                                    await asyncio.sleep(3)
                                    break
                                except Exception as e:
                                    self.logger.error(f"Failed to click 'No' button: {str(e)}")
                    else:
                        for selector in yes_button_selectors + no_button_selectors:
                            button = await self.page.query_selector(selector)
                            if button:
                                try:
                                    await button.click(force=True)
                                    self.logger.info(f"Clicked button with selector: {selector}")
                                    await asyncio.sleep(3)
                                    break
                                except Exception as e:
                                    self.logger.error(f"Failed to click button: {str(e)}")

                    try:
                        buttons = await self.page.query_selector_all('button, input[type="submit"], input[type="button"]')
                        if buttons:
                            self.logger.info(f"Found {len(buttons)} potential interactive elements on post.srf page")
                            try:
                                await buttons[0].click(force=True)
                                self.logger.info("Clicked first interactive element on page")
                                await asyncio.sleep(3)
                            except Exception as e:
                                self.logger.error(f"Failed to click first interactive element: {str(e)}")
                    except Exception as e:
                        self.logger.error(f"Error checking for interactive elements: {str(e)}")

                stay_signed_in_title = await self.page.query_selector("text=Не выходить из системы")
                stay_signed_in_title2 = await self.page.query_selector("text=Не выходить из системы?")
                stay_signed_in_title3 = await self.page.query_selector('h1:has-text("Не выходить из системы?")')
                
                if stay_signed_in_title or stay_signed_in_title2 or stay_signed_in_title3:
                    self.logger.info("Detected 'Stay signed in' question screen")

                    try:
                        await self.page.screenshot(path="stay_signed_in_screen.png")
                    except:
                        pass

                    no_button_selectors = [
                        'button[data-testid="secondaryButton"]',
                        'button:has-text("Нет")',
                        'button:has-text("No")',
                        'input[value="Нет"]',
                        'input[value="No"]'
                    ]
                    
                    no_button_found = False
                    for selector in no_button_selectors:
                        no_button = await self.page.query_selector(selector)
                        if no_button:
                            self.logger.info(f"Found 'No' button with selector: {selector}")

                            try:
                                await no_button.click(force=True)
                                self.logger.info("'No' button clicked with force=True")
                            except Exception as e:
                                self.logger.error(f"Error clicking 'No' button: {str(e)}")
                                try:
                                    await self.page.evaluate(f"document.querySelector('{selector}').click();")
                                    self.logger.info("'No' button clicked via JavaScript")
                                except Exception as js_error:
                                    self.logger.error(f"Error with JavaScript click: {str(js_error)}")
                            
                            no_button_found = True
                            break
                    
                    if not no_button_found:
                        self.logger.warning("Could not find 'No' button on stay signed in screen")

                        try:
                            all_buttons = await self.page.query_selector_all('button')
                            self.logger.info(f"Total buttons found on page: {len(all_buttons)}")
                            
                            for idx, button in enumerate(all_buttons):
                                try:
                                    button_text = await button.text_content()
                                    button_type = await button.get_attribute('type')
                                    button_class = await button.get_attribute('class')
                                    self.logger.info(f"Button {idx}: text='{button_text}', type={button_type}, class={button_class}")

                                    if button_text and ("нет" in button_text.lower() or "no" in button_text.lower()):
                                        self.logger.info(f"Found potential 'No' button by text: {button_text}")
                                        await button.click(force=True)
                                        no_button_found = True
                                        break
                                except:
                                    self.logger.info(f"Could not get info for button {idx}")
                        except Exception as e:
                            self.logger.error(f"Error examining all buttons: {str(e)}")

                    await asyncio.sleep(3)
                    continue

                stay_signed_selector = await self.page.query_selector(selectors["stay_signed_in"])
                if stay_signed_selector:
                    self.logger.info("Detected 'Stay signed in' dialog")
                    await self.page.check(selectors["stay_signed_in"])
                    await self.page.click(selectors["stay_signed_in_button"])
                    await asyncio.sleep(2)
                    continue

                skip_btn = await self.page.query_selector(selectors["skip_button"])
                if skip_btn:
                    self.logger.info("Found skip button, clicking it")
                    await self.page.click(selectors["skip_button"])
                    await asyncio.sleep(2)
                    continue

                not_now_btn = await self.page.query_selector(selectors["not_now_button"])
                if not_now_btn:
                    self.logger.info("Found 'Not now' button, clicking it")
                    await self.page.click(selectors["not_now_button"])
                    await asyncio.sleep(2)
                    continue

                verification_method = await self.page.query_selector(selectors["verification_method"])
                if verification_method:
                    self.logger.info("Found verification method selection, unable to proceed automatically")
                    return False

                security_code_field = await self.page.query_selector(selectors["security_code"])
                if security_code_field:
                    self.logger.info("Security code required (2FA), unable to proceed automatically")
                    return False

                if await self.check_login_status():
                    return True

                dialog_selectors = [
                    'div[role="dialog"]',
                    '.dialogOverlay',
                    '.modal'
                ]
                
                for dialog_selector in dialog_selectors:
                    dialog = await self.page.query_selector(dialog_selector)
                    if dialog:
                        self.logger.info(f"Found dialog with selector: {dialog_selector}")
                        try:
                            await self.page.screenshot(path="dialog_found.png")
                        except:
                            pass

                buttons = await self.page.query_selector_all('button, input[type="submit"]')
                if buttons:
                    self.logger.info(f"Found {len(buttons)} buttons on page, attempting to click the first one")
                    try:
                        await buttons[0].click(force=True)
                        self.logger.info("Clicked first button on page")
                    except Exception as e:
                        self.logger.error(f"Error clicking first button: {str(e)}")

                await asyncio.sleep(2)

            if "login.live.com/ppsecure/post.srf" in self.page.url:
                self.logger.info("Still on post.srf page after multiple attempts, trying direct navigation")
                try:
                    await self.page.goto("https://account.microsoft.com/", timeout=30000)
                    await asyncio.sleep(2)

                    new_url = self.page.url
                    if "account.microsoft.com" in new_url:
                        self.logger.info("Successfully navigated to account page")
                        return True
                    else:
                        self.logger.warning("Direct navigation did not lead to account page")
                except Exception as e:
                    self.logger.error(f"Error during direct navigation: {str(e)}")
                    
            self.logger.warning("Could not navigate through alternative login flows")
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling alternative login flows: {str(e)}")
            return False
    
    async def login(self, account: MicrosoftAccount) -> bool:
        if not self.context:
            if not await self.initialize():
                return False
        
        try:
            self.page = await self.context.new_page()

            self.page.set_default_timeout(60000)

            self.logger.info(f"Navigating to login page for account {account.email}")
            response = await self.page.goto("https://login.live.com/", timeout=60000)
            
            if not response:
                self.logger.error("Failed to navigate to login page (no response)")
                account.mark_error("Failed to navigate to login page")
                return False
            
            self.logger.info(f"Login page loaded with status {response.status}")

            try:
                await self.page.screenshot(path="login_page.png")
                self.logger.info("Login page screenshot saved")
            except Exception as e:
                self.logger.error(f"Failed to save login page screenshot: {str(e)}")

            self.logger.info(f"Entering email: {account.email}")
            await self.page.fill('input[type="email"]', account.email)

            self.logger.info("Clicking Next button after email")

            next_button_selectors = [
                'button[data-testid="primaryButton"]',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Далее")',
                'button:has-text("Next")'
            ]

            try:
                await self.page.screenshot(path="before_next_button.png")
                self.logger.info("Before 'Next' button screenshot saved")
            except Exception as e:
                self.logger.error(f"Failed to save before 'Next' button screenshot: {str(e)}")

            button_clicked = False
            for selector in next_button_selectors:
                button = await self.page.query_selector(selector)
                if button:
                    self.logger.info(f"Found Next button using selector: {selector}")
                    try:
                        await button.click(force=True)
                        self.logger.info("Next button clicked with force=True")
                        button_clicked = True
                        break
                    except Exception as e:
                        self.logger.error(f"Error clicking Next button: {str(e)}")
                        try:
                            await self.page.evaluate(f"document.querySelector('{selector}').click();")
                            self.logger.info("Next button clicked via JavaScript")
                            button_clicked = True
                            break
                        except Exception as js_error:
                            self.logger.error(f"Error with JavaScript click: {str(js_error)}")
            
            if not button_clicked:
                self.logger.warning("Could not find Next button, trying to press Enter")
                await self.page.press('input[type="email"]', 'Enter')
                self.logger.info("Pressed Enter key after email input")

            try:
                await asyncio.sleep(2)
                await self.page.screenshot(path="after_next_button.png")
                self.logger.info("After 'Next' button screenshot saved")
            except Exception as e:
                self.logger.error(f"Failed to save after 'Next' button screenshot: {str(e)}")

            try:
                self.logger.info("Waiting for password field")
                await self.page.wait_for_selector('input[type="password"]', timeout=30000)
                self.logger.info("Password field found")

                try:
                    await self.page.screenshot(path="password_page.png")
                    self.logger.info("Password page screenshot saved")
                except Exception as e:
                    self.logger.error(f"Failed to save password page screenshot: {str(e)}")

                self.logger.info("Entering password")
                await self.page.fill('input[type="password"]', account.password)

                self.logger.info("Clicking Sign in button after password")

                signin_button_selectors = [
                    'button[data-testid="primaryButton"]',
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Войти")',
                    'button:has-text("Sign in")'
                ]

                try:
                    await self.page.screenshot(path="before_signin_button.png")
                    self.logger.info("Before 'Sign in' button screenshot saved")
                except Exception as e:
                    self.logger.error(f"Failed to save before 'Sign in' button screenshot: {str(e)}")

                button_clicked = False
                for selector in signin_button_selectors:
                    button = await self.page.query_selector(selector)
                    if button:
                        self.logger.info(f"Found Sign in button using selector: {selector}")
                        try:
                            await button.click(force=True)
                            self.logger.info("Sign in button clicked with force=True")
                            button_clicked = True
                            break
                        except Exception as e:
                            self.logger.error(f"Error clicking Sign in button: {str(e)}")
                            try:
                                await self.page.evaluate(f"document.querySelector('{selector}').click();")
                                self.logger.info("Sign in button clicked via JavaScript")
                                button_clicked = True
                                break
                            except Exception as js_error:
                                self.logger.error(f"Error with JavaScript click: {str(js_error)}")
                
                if not button_clicked:
                    self.logger.warning("Could not find Sign in button, trying to press Enter")
                    await self.page.press('input[type="password"]', 'Enter')
                    self.logger.info("Pressed Enter key after password input")

                try:
                    await asyncio.sleep(2)
                    await self.page.screenshot(path="after_signin_button.png")
                    self.logger.info("After 'Sign in' button screenshot saved")
                except Exception as e:
                    self.logger.error(f"Failed to save after 'Sign in' button screenshot: {str(e)}")

                self.logger.info("Processing post-login flows")
                login_success = False

                try:
                    self.logger.info("Attempting to handle alternative login flows")
                    alt_flow_success = await self.handle_alternative_login_flows()
                    
                    if alt_flow_success:
                        self.logger.info("Alternative flow successfully handled")
                        login_success = True
                    else:
                        current_url = self.page.url
                        self.logger.info(f"Checking current URL after alternative flow attempt: {current_url}")

                        if "login.live.com/ppsecure/post.srf" in current_url:
                            self.logger.info("Still on post.srf page, attempting direct navigation to account page")
                            await self.page.goto("https://account.microsoft.com/", timeout=30000)

                            new_url = self.page.url
                            self.logger.info(f"URL after direct navigation: {new_url}")
                            
                            if "account.microsoft.com" in new_url:
                                self.logger.info("Successfully navigated to account page")
                                login_success = True
                            elif "login.live.com" in new_url:
                                self.logger.info("Redirected to login page - session not established")
                                login_success = False
                            else:
                                await self.page.goto(current_url, timeout=30000)
                                await asyncio.sleep(2)
                                
                                buttons = await self.page.query_selector_all('button, input[type="submit"], input[type="button"]')
                                if buttons and len(buttons) > 0:
                                    self.logger.info(f"Found {len(buttons)} buttons on post.srf page, clicking the most likely one")
                                    
                                    primary_button_found = False
                                    for button in buttons:
                                        class_attr = await button.get_attribute("class")
                                        if class_attr and ("primary" in class_attr.lower() or "main" in class_attr.lower()):
                                            self.logger.info("Found primary button, clicking it")
                                            await button.click(force=True)
                                            primary_button_found = True
                                            break
                                    
                                    if not primary_button_found and len(buttons) > 0:
                                        await buttons[0].click(force=True)
                                        self.logger.info("Clicked first button on post.srf page")
                                    
                                    await asyncio.sleep(3)

                                    final_url = self.page.url
                                    self.logger.info(f"URL after clicking button on post.srf: {final_url}")
                                    
                                    if "account.microsoft.com" in final_url:
                                        self.logger.info("Successfully navigated to account page after clicking button")
                                        login_success = True
                        
                        if not login_success:
                            self.logger.info("Alternative flow not successful, waiting for redirect to account page")
                            await self.page.wait_for_url("https://account.microsoft.com/*", timeout=30000)
                            self.logger.info("Successfully redirected to account page")
                            login_success = True
                
                except TimeoutError:
                    self.logger.error("Timeout waiting for account page redirect")
                    login_success = await self.check_login_errors(account)
                
                if login_success:
                    self.current_account = account
                    self.logger.info(f"Successfully logged in as {account.email}")

                    try:
                        await self.page.screenshot(path="successful_login.png")
                        self.logger.info("Successful login screenshot saved")
                    except Exception as e:
                        self.logger.error(f"Failed to save successful login screenshot: {str(e)}")
                    
                    return True
                else:
                    self.logger.error(f"Failed to log in as {account.email}")
                    return False
                
            except TimeoutError:
                self.logger.error("Timeout waiting for password field")
                account.mark_error("Timeout waiting for password field")

                error_elem = await self.page.query_selector("#usernameError")
                if error_elem:
                    error_text = await error_elem.text_content()
                    self.logger.error(f"Username error: {error_text}")
                    account.mark_error(error_text)

                try:
                    await self.page.screenshot(path="username_error.png")
                    self.logger.info("Username error screenshot saved")
                except Exception as e:
                    self.logger.error(f"Failed to save username error screenshot: {str(e)}")
                
                return False
        
        except Exception as e:
            error_msg = f"Error during login: {str(e)}"
            self.logger.error(error_msg)
            account.mark_error(error_msg)

            try:
                await self.page.screenshot(path="login_error.png")
                self.logger.info("Login error screenshot saved")
            except Exception as screenshot_error:
                self.logger.error(f"Failed to save login error screenshot: {str(screenshot_error)}")
                
            return False
    
    async def check_login_errors(self, account: MicrosoftAccount) -> bool:
        error_selectors = [
            "#usernameError",
            "#passwordError",
            "#IDErrorInput",
            ".alert-error",
            "#error",
            "#idA_IL_Error",
            ".ext-error",
            "#iSelectProofTitle",
            "[role='alert']",
            "#idTD_Error",
            ".login-error"
        ]
        
        self.logger.info("Checking for login errors")

        try:
            await self.page.screenshot(path="error_check_page.png")
            self.logger.info("Error check page screenshot saved")
        except Exception as e:
            self.logger.error(f"Failed to save error check screenshot: {str(e)}")

        current_url = self.page.url
        self.logger.info(f"Current URL during error check: {current_url}")

        if "login.live.com/ppsecure/post.srf" in current_url:
            self.logger.info("On post.srf page, attempting special handling before checking for errors")

            handled = await self.handle_post_srf_page()
            if handled:
                self.logger.info("Post.srf page successfully handled during error check")
                new_url = self.page.url
                if "account.microsoft.com" in new_url:
                    self.logger.info("Successfully reached account page after handling post.srf")
                    return True

            try:
                self.logger.info("Trying direct navigation to account page from error check")
                await self.page.goto("https://account.microsoft.com/", timeout=30000)
                await asyncio.sleep(2)

                final_url = self.page.url
                if "account.microsoft.com" in final_url:
                    self.logger.info("Successfully reached account page with direct navigation")
                    return True
                elif "login.live.com" in final_url and "login.live.com/ppsecure/post.srf" not in final_url:
                    self.logger.error("Redirected to login page - login failed")
                    account.mark_error("Session not established, redirected to login page")
            except Exception as e:
                self.logger.error(f"Error during direct navigation in error check: {str(e)}")

        for selector in error_selectors:
            error_elem = await self.page.query_selector(selector)
            if error_elem:
                try:
                    error_text = await error_elem.text_content()
                    self.logger.error(f"Login error found with selector {selector}: {error_text}")
                    account.mark_error(error_text)

                    if any(keyword in error_text.lower() for keyword in ["blocked", "suspicious", "unusual", "безопасность", "заблокирован", "подозрительн"]):
                        self.logger.error(f"Account appears to be blocked: {error_text}")
                        account.mark_blocked(error_text)
                except Exception as e:
                    self.logger.error(f"Error getting text from error element {selector}: {str(e)}")
                    account.mark_error(f"Unknown error with selector {selector}")

                try:
                    await self.page.screenshot(path=f"login_error_{selector.replace('#', '').replace('.', '')}.png")
                    self.logger.info(f"Error screenshot saved for {selector}")
                except Exception as e:
                    self.logger.error(f"Failed to save error screenshot for {selector}: {str(e)}")
                
                return False

        selectors_2fa = [
            ".proofDiv",
            "#idDiv_SAOTCAS_Title",
            "input[name='otc']",
            "#idDiv_SAOTCC_Title",
            "text=Two-step verification",
            "text=Проверка в два этапа"
        ]
        
        for selector in selectors_2fa:
            element_2fa = await self.page.query_selector(selector)
            if element_2fa:
                try:
                    element_text = await element_2fa.text_content()
                    error_msg = f"Two-factor authentication required: {element_text}"
                except:
                    error_msg = "Two-factor authentication required but not supported"
                
                self.logger.error(error_msg)
                account.mark_error(error_msg)

                try:
                    await self.page.screenshot(path="2fa_required.png")
                    self.logger.info("2FA required screenshot saved")
                except Exception as e:
                    self.logger.error(f"Failed to save 2FA screenshot: {str(e)}")
                
                return False

        try:
            page_text = await self.page.evaluate("document.body.innerText")
            error_keywords = [
                "incorrect password", "неверный пароль",
                "account doesn't exist", "аккаунт не существует",
                "there was an issue", "возникла проблема",
                "try again later", "повторите попытку позже",
                "account has been locked", "аккаунт заблокирован",
                "suspicious activity", "подозрительная активность"
            ]
            
            for keyword in error_keywords:
                if keyword.lower() in page_text.lower():
                    error_msg = f"Detected error text on page: {keyword}"
                    self.logger.error(error_msg)
                    account.mark_error(error_msg)

                    if any(block_keyword in keyword.lower() for block_keyword in ["locked", "suspicious", "заблокирован", "подозрительн"]):
                        account.mark_blocked(error_msg)
                    
                    return False
        except Exception as e:
            self.logger.error(f"Error checking page text: {str(e)}")

        if "account.microsoft.com" in current_url:
            self.logger.info("Login appears successful based on URL")
            return True

        if "login.live.com/ppsecure/post.srf" in current_url:
            self.logger.info("No error found but still on post.srf page, login state unclear")

            try:
                await asyncio.sleep(3)

                success_indicators = [
                    'div:has-text("Welcome")',
                    'div:has-text("Добро пожаловать")',
                    'h1:has-text("Microsoft account")',
                    'h1:has-text("Учетная запись Майкрософт")'
                ]
                
                for indicator in success_indicators:
                    if await self.page.query_selector(indicator):
                        self.logger.info(f"Found success indicator: {indicator}")
                        return True
            except Exception as e:
                self.logger.error(f"Error during additional post.srf check: {str(e)}")

        self.logger.error(f"Unknown login error, current URL: {current_url}")
        account.mark_error("Unknown login error")

        try:
            await self.page.screenshot(path="unknown_error.png")
            self.logger.info("Unknown error screenshot saved")
        except Exception as e:
            self.logger.error(f"Failed to save unknown error screenshot: {str(e)}")
        
        return False
    
    async def navigate_to_redeem_page(self) -> bool:
        if not self.page or not self.current_account:
            self.logger.error("Not logged in, can't navigate to redeem page")
            return False
        
        try:
            try:
                await self.page.screenshot(path="before_redeem_navigation.png")
            except:
                pass

            page_load_timeout = 90000
            self.logger.info(f"Navigating to redeem page: {config.redeem_url} with timeout {page_load_timeout}ms")

            self.page.set_default_timeout(page_load_timeout)

            try:
                response = await self.page.goto(config.redeem_url, timeout=page_load_timeout)
                
                if not response:
                    self.logger.error("Failed to navigate to redeem page (no response)")
                    if self.current_account:
                        self.current_account.mark_error("Failed to navigate to redeem page")
                    return False
                
                self.logger.info(f"Redeem page response status: {response.status}")
            except Exception as e:
                self.logger.error(f"Error during initial navigation to redeem page: {str(e)}")

                self.logger.info("Attempting alternative navigation approach with multiple retries")
                return await self._navigate_with_retries(config.redeem_url, max_retries=3)

            try:
                await self.page.wait_for_load_state("networkidle", timeout=60000)
                self.logger.info("Page reached networkidle state")
            except Exception as e:
                self.logger.warning(f"Timeout waiting for networkidle, continuing anyway: {str(e)}")

            await asyncio.sleep(3)

            try:
                await self.page.screenshot(path="after_redeem_navigation.png")
            except:
                pass

            frames = self.page.frames
            self.logger.info(f"Found {len(frames)} frames on the page")

            if len(frames) <= 1:
                self.logger.info("Few frames detected, waiting for more frames to load...")
                for _ in range(3):
                    await asyncio.sleep(5)
                    frames = self.page.frames
                    self.logger.info(f"Now found {len(frames)} frames after waiting")
                    if len(frames) > 1:
                        break

            self.logger.info("Checking for cookie dialogs")

            try:
                accept_button_selectors = [
                    'button:has-text("Принять")',
                    'button:has-text("Accept")',
                    'button:has-text("Agree")',
                    'button:has-text("Разрешить")'
                ]
                
                for selector in accept_button_selectors:
                    try:
                        accept_button = await self.page.query_selector(selector)
                        if accept_button:
                            self.logger.info(f"Found accept cookie button with selector: {selector}")
                            await accept_button.click()
                            self.logger.info("Cookies accepted")
                            await asyncio.sleep(2)
                            break
                    except Exception as e:
                        self.logger.debug(f"Error finding cookie button {selector}: {str(e)}")

                for frame in frames:
                    for selector in accept_button_selectors:
                        try:
                            cookie_btn = await frame.query_selector(selector)
                            if cookie_btn:
                                self.logger.info(f"Found accept cookie button in frame: {selector}")
                                await cookie_btn.click()
                                self.logger.info("Cookies accepted in frame")
                                await asyncio.sleep(2)
                        except Exception as e:
                            self.logger.debug(f"Error finding cookie button in frame: {str(e)}")
            except Exception as e:
                self.logger.debug(f"Error handling cookie dialog: {str(e)}")

            input_field = None
            target_frame = None

            for i, frame in enumerate(frames):
                try:
                    frame_url = frame.url
                    self.logger.info(f"Frame {i} URL: {frame_url}")

                    try:
                        await self.page.screenshot(path=f"frame_{i}_content.png")
                    except:
                        pass
                    
                    if any(keyword in frame_url.lower() for keyword in ["redeem", "billing", "store"]):
                        self.logger.info(f"Analyzing frame {i} for input field")

                        input_selectors = [
                            'input[aria-label="Enter code"]',
                            'input[aria-label="Введите 25-значный код"]',
                            'input[name="tokenString"]',
                            'input.input--mKKIbi6U',
                            'input[placeholder="Введите 25-значный код"]',
                            'input[placeholder="Enter 25-character code"]',
                            'input[type="text"][autocomplete="off"][maxlength="29"]',
                            'input[type="text"]'
                        ]

                        for selector in input_selectors:
                            try:
                                self.logger.info(f"Looking for input with selector: {selector} in frame {i}")
                                field = await frame.query_selector(selector)
                                if field:
                                    self.logger.info(f"Found input field in frame {i} with selector: {selector}")
                                    input_field = field
                                    target_frame = frame
                                    return True
                            except Exception as e:
                                self.logger.debug(f"Error finding selector {selector} in frame {i}: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Error analyzing frame {i}: {str(e)}")

            if any("redeem" in frame.url.lower() or 
                  "billing" in frame.url.lower() or 
                  "store" in frame.url.lower() for frame in frames):
                self.logger.info("Found relevant frame but no input yet, waiting for elements to load...")
                await asyncio.sleep(5)

                await self.page.screenshot(path="waiting_for_input_field.png")

                for i, frame in enumerate(frames):
                    if any(keyword in frame.url.lower() for keyword in ["redeem", "billing", "store"]):
                        input_field = await frame.query_selector('input[type="text"]')
                        if input_field:
                            self.logger.info(f"Found input field in frame {i} after waiting")
                            return True

                self.logger.info("Found relevant frame, considering navigation successful")
                return True

            input_selectors = [
                'input[aria-label="Enter code"]',
                'input[aria-label="Введите 25-значный код"]',
                'input[name="tokenString"]',
                'input.input--mKKIbi6U',
                'input[placeholder="Введите 25-значный код"]',
                'input[placeholder="Enter 25-character code"]',
                'input[type="text"][autocomplete="off"][maxlength="29"]',
                'input[type="text"]'
            ]
            
            for selector in input_selectors:
                field = await self.page.query_selector(selector)
                if field:
                    self.logger.info(f"Found input field on main page with selector: {selector}")
                    return True

            current_url = self.page.url
            if "redeem" in current_url.lower() or "billing" in current_url.lower():
                self.logger.info(f"On redeem/billing page based on URL: {current_url}")
                return True

            alternative_urls = [
                "https://www.microsoft.com/store/redemption",
                "https://redeem.microsoft.com",
                "https://account.microsoft.com/billing/store"
            ]
            
            for url in alternative_urls:
                self.logger.info(f"Trying alternative redeem URL: {url}")
                try:
                    await self.page.goto(url, timeout=30000)
                    await asyncio.sleep(3)

                    new_url = self.page.url
                    if "redeem" in new_url.lower() or "billing" in new_url.lower():
                        self.logger.info(f"Successfully navigated to redeem page: {new_url}")
                        return True
                except Exception as e:
                    self.logger.error(f"Error navigating to {url}: {str(e)}")
            
            self.logger.error("Failed to find redeem input field")
            return False
            
        except Exception as e:
            error_msg = f"Error navigating to redeem page: {str(e)}"
            self.logger.error(error_msg)
            if self.current_account:
                self.current_account.mark_error(error_msg)
            return False
    
    async def _navigate_with_retries(self, url: str, max_retries: int = 3) -> bool:
        """Осуществляет навигацию с повторными попытками"""
        self.logger.info(f"Attempting navigation to {url} with {max_retries} retries")
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Navigation attempt {attempt+1}/{max_retries}")

                timeout = 60000 * (attempt + 1)
                self.page.set_default_timeout(timeout)

                await self.page.goto(url, timeout=timeout)

                await asyncio.sleep(5 + attempt * 2)

                frames = self.page.frames
                self.logger.info(f"Found {len(frames)} frames after attempt {attempt+1}")

                for idx, frame in enumerate(frames):
                    try:
                        if "redeem" in frame.url.lower() or "billing" in frame.url.lower() or "store" in frame.url.lower():
                            # Ищем поле ввода во фрейме
                            input_field = await frame.query_selector('input[name="tokenString"], input[type="text"]')
                            if input_field:
                                self.logger.info(f"Found input field in frame {idx} after retry {attempt+1}")
                                return True
                    except Exception as frame_err:
                        self.logger.debug(f"Error checking frame {idx}: {str(frame_err)}")

                if any("redeem" in frame.url.lower() or 
                       "billing" in frame.url.lower() or 
                       "store" in frame.url.lower() for frame in frames):
                    self.logger.info("Found relevant frame, considering navigation successful")
                    return True

                current_url = self.page.url
                if "redeem" in current_url or "billing" in current_url or "store" in current_url:
                    self.logger.info(f"URL contains relevant keywords: {current_url}")
                    has_elements = await self.page.query_selector('input[type="text"], form, button[type="submit"]')
                    if has_elements:
                        self.logger.info("Found relevant elements on page, navigation considered successful")
                        return True
                
            except Exception as e:
                self.logger.error(f"Error during retry {attempt+1}: {str(e)}")

            if attempt < max_retries - 1:
                await asyncio.sleep(3)
        
        self.logger.error(f"Failed to navigate to {url} after {max_retries} attempts")

        try:
            await self.page.screenshot(path=f"navigation_failed_{int(time.time())}.png")
            self.logger.info("Saved screenshot of failed navigation state")
        except Exception as ss_err:
            self.logger.error(f"Failed to save screenshot: {str(ss_err)}")
        
        return False
    
    async def logout(self) -> bool:
        if not self.page or not self.current_account:
            return True
        
        try:
            current_url = self.page.url
            self.logger.info(f"Current URL before logout: {current_url}")

            if "login.live.com" in current_url:
                self.current_account = None
                self.logger.info("Already logged out (on login page)")
                return True

            self.logger.info("Navigating to account page for logout")
            await self.page.goto("https://account.microsoft.com/", timeout=30000)

            await asyncio.sleep(2)

            try:
                await self.page.screenshot(path="before_logout.png")
            except:
                pass

            logout_methods = [
                self._logout_via_account_button,
                self._logout_via_direct_links,
                self._logout_via_javascript,
                self._logout_via_direct_url
            ]
            
            for method in logout_methods:
                try:
                    self.logger.info(f"Trying logout method: {method.__name__}")
                    success = await method()
                    if success:
                        self.current_account = None
                        self.logger.info(f"Successfully logged out using {method.__name__}")
                        return True
                except Exception as e:
                    self.logger.error(f"Error during {method.__name__}: {str(e)}")

            self.logger.warning("All logout methods failed, resetting page")
            try:
                await self.page.close()
                self.page = await self.context.new_page()
                self.current_account = None
                return True
            except Exception as close_err:
                self.logger.error(f"Error closing page: {str(close_err)}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error during logout: {str(e)}")

            try:
                await self.page.close()
                self.page = await self.context.new_page()
                self.current_account = None
                return True
            except Exception as close_err:
                self.logger.error(f"Error closing page after logout failure: {str(close_err)}")
                return False
    
    async def _logout_via_account_button(self) -> bool:
        try:
            self.logger.info("Clicking on account button")

            account_button_selectors = [
                'button[aria-label*="Account"]',
                '[aria-label*="account"]',
                '.ms-Button--icon',
                '.mectrl_headertext',
                'img[title*="Account"]',
                'img[alt*="Account"]',
                'img[alt*="account"]',
                '.account-image',
                '#mectrl_headerPicture',
                '#mectrl_main_trigger'
            ]
            
            button_clicked = False
            for selector in account_button_selectors:
                account_button = await self.page.query_selector(selector)
                if account_button:
                    self.logger.info(f"Found account button with selector: {selector}")
                    await account_button.click()
                    button_clicked = True
                    break
            
            if not button_clicked:
                self.logger.warning("Could not find account button")
                return False

            await asyncio.sleep(2)

            try:
                await self.page.screenshot(path="account_menu_open.png")
            except:
                pass

            self.logger.info("Clicking on sign out link")

            signout_selectors = [
                'a[data-bi-id*="signout"]',
                'a:has-text("Sign out")',
                'a:has-text("Выйти")',
                '#meControlSignoutLink',
                'a[href*="logout"]',
                'a[href*="signout"]',
                'a[id*="signout"]',
                'a[class*="signout"]'
            ]
            
            signout_clicked = False
            for selector in signout_selectors:
                signout_link = await self.page.query_selector(selector)
                if signout_link:
                    self.logger.info(f"Found sign out link with selector: {selector}")
                    await signout_link.click()
                    signout_clicked = True

                    try:
                        await self.page.wait_for_url("https://*.live.com/login.srf*", timeout=15000)
                        return True
                    except:
                        current_url = self.page.url
                        if "login.live.com" in current_url:
                            return True
            
            if not signout_clicked:
                self.logger.warning("Could not find sign out link")
                return False
            
            return False
        except Exception as e:
            self.logger.error(f"Error in _logout_via_account_button: {str(e)}")
            return False
    
    async def _logout_via_direct_links(self) -> bool:
        try:
            links = await self.page.query_selector_all('a')
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()

                    if href and ('logout' in href.lower() or 'signout' in href.lower()):
                        self.logger.info(f"Found logout link by href: {href}")
                        await link.click()
                        await asyncio.sleep(2)

                        current_url = self.page.url
                        if "login.live.com" in current_url:
                            return True
                    
                    if text and ('sign out' in text.lower() or 'выйти' in text.lower() or 'logout' in text.lower()):
                        self.logger.info(f"Found logout link by text: {text}")
                        await link.click()
                        await asyncio.sleep(2)

                        current_url = self.page.url
                        if "login.live.com" in current_url:
                            return True
                except Exception as e:
                    self.logger.debug(f"Error processing link: {str(e)}")
            
            return False
        except Exception as e:
            self.logger.error(f"Error in _logout_via_direct_links: {str(e)}")
            return False
    
    async def _logout_via_javascript(self) -> bool:
        try:
            js_result = await self.page.evaluate("""() => {
                const allElements = document.querySelectorAll('a, button, div, span');
                for (let elem of allElements) {
                    if (elem.innerText && 
                        (elem.innerText.toLowerCase().includes('sign out') || 
                         elem.innerText.toLowerCase().includes('выйти') || 
                         elem.innerText.toLowerCase().includes('logout'))) {
                        elem.click();
                        return true;
                    }
                }
                
                const links = document.querySelectorAll('a[href*="logout"], a[href*="signout"]');
                if (links.length > 0) {
                    links[0].click();
                    return true;
                }
                
                const idElements = document.querySelectorAll('[id*="signout"], [id*="logout"], [class*="signout"], [class*="logout"]');
                if (idElements.length > 0) {
                    idElements[0].click();
                    return true;
                }
                
                return false;
            }""")
            
            self.logger.info(f"JavaScript logout attempt result: {js_result}")
            
            if js_result:
                await asyncio.sleep(3)
                current_url = self.page.url
                if "login.live.com" in current_url:
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error in _logout_via_javascript: {str(e)}")
            return False
    
    async def _logout_via_direct_url(self) -> bool:
        try:
            logout_urls = [
                "https://login.live.com/logout.srf",
                "https://login.microsoftonline.com/logout.srf",
                "https://account.microsoft.com/auth/global-signout"
            ]
            
            for url in logout_urls:
                self.logger.info(f"Trying direct logout URL: {url}")
                await self.page.goto(url, timeout=20000)
                await asyncio.sleep(2)

                current_url = self.page.url
                if "login.live.com" in current_url or "login.microsoftonline.com" in current_url:
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error in _logout_via_direct_url: {str(e)}")
            return False
    
    async def check_login_status(self) -> bool:
        if not self.page or not self.current_account:
            return False
        
        try:
            self.logger.info("Checking login status")
            response = await self.page.goto("https://account.microsoft.com/", timeout=30000)
            
            if not response:
                self.logger.error("Failed to navigate to account page (no response)")
                return False
            
            self.logger.info(f"Account page response status: {response.status}")

            current_url = self.page.url
            self.logger.info(f"Current URL after navigation: {current_url}")
            
            if "login.live.com" in current_url:
                self.logger.info("Session expired, no longer logged in")
                self.current_account = None
                return False

            try:
                await self.page.screenshot(path="login_status_check.png")
            except:
                pass
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error checking login status: {str(e)}")
            return False
    
    async def handle_post_srf_page(self) -> bool:
        try:
            current_url = self.page.url
            if "login.live.com/ppsecure/post.srf" not in current_url:
                return False
            
            self.logger.info("Handling post.srf page specifically")

            try:
                await self.page.screenshot(path="post_srf_specific_handler.png")
            except:
                pass

            stay_signed_text_selectors = [
                'div:has-text("Не выходить из системы?")',
                'div:has-text("Stay signed in?")',
                'h1:has-text("Не выходить из системы?")',
                'h1:has-text("Stay signed in?")',
                'p:has-text("Не выходить из системы?")',
                'p:has-text("Stay signed in?")'
            ]
            
            stay_signed_found = False
            for selector in stay_signed_text_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    stay_signed_found = True
                    self.logger.info(f"Found 'Stay signed in' text with selector: {selector}")
                    break
            
            if stay_signed_found:
                no_button_selectors = [
                    'button[data-testid="secondaryButton"]',
                    'button:has-text("Нет")',
                    'button:has-text("No")',
                    'input[value="Нет"]',
                    'input[value="No"]'
                ]
                
                for selector in no_button_selectors:
                    button = await self.page.query_selector(selector)
                    if button:
                        try:
                            self.logger.info(f"Clicking 'No' button with selector: {selector}")
                            await button.click(force=True)
                            await asyncio.sleep(3)
                            return True
                        except Exception as e:
                            self.logger.error(f"Error clicking 'No' button: {str(e)}")
                            try:
                                await self.page.evaluate(f"document.querySelector('{selector}').click();")
                                self.logger.info("Clicked 'No' button via JavaScript")
                                await asyncio.sleep(3)
                                return True
                            except Exception as js_error:
                                self.logger.error(f"Error with JavaScript click: {str(js_error)}")

                buttons = await self.page.query_selector_all('button')
                if len(buttons) >= 2:
                    try:
                        self.logger.info("Clicking second button (assuming it's 'No')")
                        await buttons[1].click(force=True)
                        await asyncio.sleep(3)
                        return True
                    except Exception as e:
                        self.logger.error(f"Error clicking second button: {str(e)}")

            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[data-testid="primaryButton"]',
                'button[data-testid="secondaryButton"]'
            ]
            
            for selector in button_selectors:
                button = await self.page.query_selector(selector)
                if button:
                    try:
                        self.logger.info(f"Clicking button with selector: {selector}")
                        await button.click(force=True)
                        await asyncio.sleep(3)
                        return True
                    except Exception as e:
                        self.logger.error(f"Error clicking button: {str(e)}")

            all_buttons = await self.page.query_selector_all('button, input[type="submit"], input[type="button"]')
            if all_buttons:
                self.logger.info(f"Found {len(all_buttons)} potential buttons on page")

                for button in all_buttons:
                    try:
                        button_text = await button.text_content()
                        if button_text and any(text in button_text.lower() for text in ["продолжить", "continue", "далее", "next"]):
                            self.logger.info(f"Found continue button with text: {button_text}")
                            await button.click(force=True)
                            await asyncio.sleep(3)
                            return True
                    except:
                        pass

                if len(all_buttons) > 0:
                    try:
                        self.logger.info("Clicking first button on page as fallback")
                        await all_buttons[0].click(force=True)
                        await asyncio.sleep(3)
                        return True
                    except Exception as e:
                        self.logger.error(f"Error clicking first button: {str(e)}")

            try:
                self.logger.info("Attempting direct navigation to account.microsoft.com")
                await self.page.goto("https://account.microsoft.com/", timeout=30000)
                await asyncio.sleep(2)
                
                new_url = self.page.url
                if "account.microsoft.com" in new_url:
                    self.logger.info("Successfully navigated to account page")
                    return True
                else:
                    self.logger.info(f"Navigation resulted in URL: {new_url}")
            except Exception as e:
                self.logger.error(f"Error during direct navigation: {str(e)}")
            
            return False
        except Exception as e:
            self.logger.error(f"Error handling post.srf page: {str(e)}")
            return False
    
    async def check_key(self, key: str) -> dict:
        if not self.page or not self.current_account:
            return {"status": "error", "message": "Не авторизован"}
        
        try:
            if not await self.navigate_to_redeem_page():
                return {"status": "error", "message": "Не удалось перейти на страницу проверки ключей"}

            try:
                await self.page.screenshot(path="before_key_check.png")
                self.logger.info("Screenshot before key check saved")
            except Exception as e:
                self.logger.error(f"Failed to save before key check screenshot: {str(e)}")

            await asyncio.sleep(5)

            self.logger.info("Проверка наличия диалога с куки")

            try:
                accept_button_selectors = [
                    'button:has-text("Принять")',
                    'button:has-text("Accept")',
                    'button:has-text("Agree")',
                    'button:has-text("Разрешить")'
                ]
                
                for selector in accept_button_selectors:
                    try:
                        accept_button = await self.page.query_selector(selector)
                        if accept_button:
                            self.logger.info(f"Найдена кнопка принятия куки по селектору: {selector}")
                            await accept_button.click()
                            self.logger.info("Куки приняты")
                            await asyncio.sleep(2)
                            break
                    except Exception as e:
                        self.logger.debug(f"Ошибка при поиске кнопки куки {selector}: {str(e)}")

                frames = self.page.frames
                for frame in frames:
                    for selector in accept_button_selectors:
                        try:
                            cookie_btn = await frame.query_selector(selector)
                            if cookie_btn:
                                self.logger.info(f"Найдена кнопка принятия куки в фрейме: {selector}")
                                await cookie_btn.click()
                                self.logger.info("Куки приняты во фрейме")
                                await asyncio.sleep(2)
                        except Exception as e:
                            self.logger.debug(f"Ошибка при поиске кнопки куки во фрейме: {str(e)}")
            except Exception as e:
                self.logger.debug(f"Ошибка при обработке диалога с куки: {str(e)}")

            await self.page.screenshot(path="after_cookies_handled.png")

            frames = self.page.frames
            self.logger.info(f"Обнаружено фреймов на странице: {len(frames)}")

            input_field = None
            target_frame = None

            for i, frame in enumerate(frames):
                try:
                    frame_url = frame.url
                    self.logger.info(f"Фрейм {i}: {frame_url}")
                    
                    if any(keyword in frame_url.lower() for keyword in ["redeem", "billing", "store"]):
                        self.logger.info(f"Анализирую фрейм {i} для поиска поля ввода")

                        try:
                            await self.page.screenshot(path=f"frame_{i}_content.png")
                        except:
                            pass

                        input_selectors = [
                            'input[aria-label="Enter code"]',
                            'input[aria-label="Введите 25-значный код"]',
                            'input[name="tokenString"]',
                            'input.input--mKKIbi6U',
                            'input[placeholder="Введите 25-значный код"]',
                            'input[placeholder="Enter 25-character code"]',
                            'input[type="text"][autocomplete="off"][maxlength="29"]',
                            'input[type="text"]'
                        ]

                        for selector in input_selectors:
                            try:
                                self.logger.info(f"Ищу поле ввода с селектором: {selector} в фрейме {i}")
                                field = await frame.query_selector(selector)
                                if field:
                                    self.logger.info(f"Найдено поле ввода в фрейме {i} по селектору: {selector}")
                                    input_field = field
                                    target_frame = frame
                                    break
                            except Exception as e:
                                self.logger.debug(f"Ошибка при поиске селектора {selector} в фрейме {i}: {str(e)}")
                        
                        if input_field:
                            break
                except Exception as e:
                    self.logger.error(f"Ошибка при анализе фрейма {i}: {str(e)}")

            if not input_field:
                for selector in input_selectors:
                    try:
                        field = await self.page.query_selector(selector)
                        if field:
                            self.logger.info(f"Найдено поле ввода на основной странице по селектору: {selector}")
                            input_field = field
                            break
                    except Exception as e:
                        self.logger.debug(f"Ошибка при поиске селектора {selector} на основной странице: {str(e)}")

            if not input_field:
                self.logger.error("❌ Не удалось найти поле для ввода ключа")
                await self.page.screenshot(path="no_input_field_found.png")
                return {"status": "error", "message": "Не удалось найти поле ввода ключа"}

            self.logger.info(f"Ввод ключа: {key}")
            await input_field.fill("")
            await input_field.type(key, delay=50)

            await self.page.screenshot(path="key_entered.png")
            self.logger.info("Ключ введен, ожидаем автоматической проверки")

            self.logger.info("Ожидание результата автоматической проверки")

            for i in range(15):
                await self.page.screenshot(path=f"checking_key_{i}.png")
                self.logger.info(f"Ожидание проверки ключа: {i+1}/15 секунд")

                cookie_dialog_found = False
                for frame in frames:
                    try:
                        for cookie_selector in ['div:has-text("файлы cookie")', 'div:has-text("cookies")', 'button:has-text("Принять")', 'button:has-text("Accept")']:
                            try:
                                cookie_dialog = await frame.query_selector(cookie_selector)
                                if cookie_dialog:
                                    self.logger.info(f"Обнаружен диалог с файлами cookie в фрейме")
                                    cookie_dialog_found = True

                                    for accept_selector in ['button:has-text("Принять")', 'button:has-text("Accept")', 'button:has-text("Разрешить")']:
                                        try:
                                            accept_btn = await frame.query_selector(accept_selector)
                                            if accept_btn:
                                                self.logger.info(f"Нажимаю кнопку принятия куки: {accept_selector}")
                                                await accept_btn.click()
                                                await asyncio.sleep(1)
                                                break
                                        except Exception as e:
                                            self.logger.debug(f"Ошибка при нажатии кнопки куки: {str(e)}")
                            except Exception:
                                pass
                    except Exception:
                        pass

                for cookie_selector in ['button:has-text("Принять")', 'button:has-text("Accept")']:
                    try:
                        cookie_btn = await self.page.query_selector(cookie_selector)
                        if cookie_btn:
                            self.logger.info("Нажимаю кнопку принятия куки на основной странице")
                            await cookie_btn.click()
                            await asyncio.sleep(1)
                            break
                    except Exception:
                        pass

                current_url = self.page.url
                if "success" in current_url.lower() or "confirmed" in current_url.lower():
                    self.logger.info("✅ Успешная активация определена по URL")
                    return {"status": "success", "message": "Ключ активирован"}

                if not cookie_dialog_found:
                    if target_frame:
                        result = await self._check_key_result_in_frame(target_frame)
                        if result["status"] != "unknown":
                            return result
                    
                    errors_found = False
                    error_message = ""

                    for frame in frames:
                        try:
                            error_selectors = [
                                '.errorContainer--Xj5VIIIy',
                                '.errorMessageText--NWPmAAeE',
                                '[role="alert"]',
                                '[class*="error"]',
                                'div:has-text("код отключен")',
                                'div:has-text("уже использован")',
                                'div:has-text("недействителен")'
                            ]
                            
                            for selector in error_selectors:
                                try:
                                    error_elem = await frame.query_selector(selector)
                                    if error_elem:
                                        error_text = await error_elem.text_content()
                                        error_text_lower = error_text.lower()
                                        if error_text.strip() and "cookie" not in error_text_lower and "файл" not in error_text_lower:
                                            self.logger.error(f"Обнаружена ошибка: {error_text}")
                                            errors_found = True
                                            error_message = error_text
                                            
                                            if "отключен" in error_text_lower or "disabled" in error_text_lower:
                                                return {"status": "disabled", "message": error_text}
                                            elif "использован" in error_text_lower or "used" in error_text_lower:
                                                return {"status": "used", "message": error_text}
                                            elif "недействителен" in error_text_lower or "invalid" in error_text_lower:
                                                return {"status": "invalid", "message": error_text}
                                            else:
                                                return {"status": "error", "message": error_text}
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    success_found = False
                    success_message = ""

                    for frame in frames:
                        try:
                            success_selectors = [
                                'div:has-text("Активировано")',
                                'div:has-text("Activated")',
                                'div.successContainer--nGBnuzHv',
                                'h1:has-text("Теперь у вас есть")',
                                'h1:has-text("You now have")',
                                '[class*="success"]'
                            ]
                            
                            for selector in success_selectors:
                                try:
                                    success_elem = await frame.query_selector(selector)
                                    if success_elem:
                                        success_text = await success_elem.text_content()
                                        if success_text.strip():
                                            self.logger.info(f"✅ Успешная активация: {success_text}")
                                            success_found = True
                                            success_message = success_text
                                            return {"status": "success", "message": success_text}
                                except Exception:
                                    pass
                        except Exception:
                            pass

                await asyncio.sleep(1)

            await self.page.screenshot(path="final_state.png")

            try:
                page_content = await self.page.content()
                page_text_lower = page_content.lower()
                
                if ("активировано" in page_text_lower or 
                    "activated" in page_text_lower or 
                    "success" in page_text_lower or 
                    "успех" in page_text_lower):
                    self.logger.info("✅ Обнаружен текст успешной активации на странице")
                    return {"status": "success", "message": "Ключ активирован успешно"}
                elif "отключен" in page_text_lower or "disabled" in page_text_lower:
                    return {"status": "disabled", "message": "Ключ отключен"}
                elif "использован" in page_text_lower or "used" in page_text_lower:
                    return {"status": "used", "message": "Ключ уже использован"}
                elif "недействителен" in page_text_lower or "invalid" in page_text_lower:
                    return {"status": "invalid", "message": "Недействительный ключ"}
            except Exception as e:
                self.logger.error(f"Ошибка при получении содержимого страницы: {str(e)}")

            self.logger.info("Результат проверки ключа не определен")
            return {"status": "unknown", "message": "Неопределенный статус ключа"}
            
        except Exception as e:
            error_msg = f"Ошибка при проверке ключа: {str(e)}"
            self.logger.error(error_msg)
            await self.page.screenshot(path="unexpected_error.png")
            return {"status": "error", "message": error_msg}
    
    async def _check_key_result_in_frame(self, frame) -> dict:
        try:
            error_selectors = [
                '.errorContainer--Xj5VIIIy',
                '.errorMessageText--NWPmAAeE',
                '[role="alert"]',
                'div.infoContainer--LaCo6Qwb',
                'p:has-text("код отключен")',
                'p:has-text("уже использован")',
                'p:has-text("недействителен")',
                '[class*="error"]'
            ]

            error_element = None
            for selector in error_selectors:
                try:
                    element = await frame.query_selector(selector)
                    if element:
                        error_element = element
                        break
                except Exception as e:
                    self.logger.debug(f"Error checking error selector {selector}: {str(e)}")
            
            if error_element:
                try:
                    error_text = await error_element.text_content()
                    self.logger.error(f"Error message found in frame: {error_text}")
                    
                    error_text_lower = error_text.lower()
                    if "отключен" in error_text_lower or "disabled" in error_text_lower:
                        return {"status": "disabled", "message": error_text}
                    elif "использован" in error_text_lower or "used" in error_text_lower:
                        return {"status": "used", "message": error_text}
                    elif "недействителен" in error_text_lower or "invalid" in error_text_lower:
                        return {"status": "invalid", "message": error_text}
                    else:
                        return {"status": "error", "message": error_text}
                except Exception as e:
                    self.logger.error(f"Error getting error element text: {str(e)}")

            success_selectors = [
                'div:has-text("Активировано")',
                'div:has-text("Activated")',
                'div.successContainer--nGBnuzHv',
                'h1:has-text("Теперь у вас есть")',
                'h1:has-text("You now have")',
                '[class*="success"]',
                'h1', 
                'h2'
            ]

            success_element = None
            for selector in success_selectors:
                try:
                    element = await frame.query_selector(selector)
                    if element:
                        success_element = element
                        break
                except Exception as e:
                    self.logger.debug(f"Error checking success selector {selector}: {str(e)}")
            
            if success_element:
                try:
                    success_text = await success_element.text_content()
                    self.logger.info(f"Success message found in frame: {success_text}")
                    return {"status": "success", "message": success_text}
                except Exception as e:
                    self.logger.error(f"Error getting success element text: {str(e)}")
                    return {"status": "success", "message": "Ключ активирован успешно"}

            try:
                page_text = await frame.evaluate("document.body.innerText")
                page_text_lower = page_text.lower()
                
                if ("активировано" in page_text_lower or "activated" in page_text_lower or 
                    "success" in page_text_lower or "успех" in page_text_lower):
                    return {"status": "success", "message": "Ключ активирован успешно"}
            except Exception as e:
                self.logger.error(f"Error checking page text for success: {str(e)}")

            manage_selectors = [
                'button:has-text("Управление")',
                'button:has-text("Manage")',
                'a:has-text("Управление")',
                'a:has-text("Manage")',
                'a[href*="subscription"]',
                'a[href*="product"]'
            ]
            
            has_manage_button = False
            for selector in manage_selectors:
                try:
                    button = await frame.query_selector(selector)
                    if button:
                        has_manage_button = True
                        break
                except Exception as e:
                    self.logger.debug(f"Error checking manage button selector {selector}: {str(e)}")
            
            if has_manage_button:
                self.logger.info("Found management button, activation successful")
                return {"status": "success", "message": "Ключ активирован успешно"}

            return {"status": "unknown", "message": "Неопределенный статус ключа"}
            
        except Exception as e:
            self.logger.error(f"Error checking key result in frame: {str(e)}")
            return {"status": "error", "message": f"Ошибка при проверке результата: {str(e)}"}
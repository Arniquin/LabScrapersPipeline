import os
import random
import time
import requests
import zipfile
import re
from typing import Tuple, List, Optional

# Usamos el webdriver estándar para evitar el error de desired_capabilities
from selenium import webdriver 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

# Safely import Mage AI secrets manager
try:
    from mage_ai.data_preparation.shared.secrets import get_secret
except ImportError:
    get_secret = lambda key: os.environ.get(key)

# Type Alias
Locator = Tuple[By, str]

class BaseScraper:
    def __init__(self, driver=None, default_timeout: int = 30):
        self.driver = driver
        self.timeout = default_timeout
        if self.driver:
            self.wait = WebDriverWait(self.driver, self.timeout)

    @classmethod
    def test_proxy(cls, proxy_url: str) -> bool:
        """Lightweight pre-flight check using Decodo's IP endpoint."""
        print("Testing Decodo proxy connection...")
        try:
            test_result = requests.get(
                'https://ip.decodo.com/json', 
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=10
            )
            test_result.raise_for_status()
            ip_data = test_result.json()
            print(f"Proxy Active! Current IP: {ip_data.get('ip')} in {ip_data.get('country')}")
            return True
        except Exception as e:
            print(f"Proxy test failed: {e}")
            return False

    @classmethod
    def create_with_decodo(cls, port: int = 20001, timeout: int = 30, headless: bool = True):
        username = get_secret('DECODO_USERNAME')
        password = get_secret('DECODO_PASSWORD')

        if not username or not password:
            raise ValueError("Decodo credentials not found in Mage Secrets.")

        proxy_url = f"http://{username}:{password}@mx.decodo.com:{port}"

        if not cls.test_proxy(proxy_url):
            raise ConnectionError("Aborting Selenium initialization: Proxy test failed.")

        return cls.create_with_driver(proxy_url=proxy_url, timeout=timeout, headless=headless)

    @classmethod
    def create_with_driver(cls, proxy_url: str = None, timeout: int = 30, headless: bool = True):
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        # Bandwidth Saver
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.media_stream": 2
        }
        options.add_experimental_option("prefs", prefs)

        # Lógica de Autenticación mediante Extensión (Solución al error de SeleniumWire)
        if proxy_url:
            # Extraemos credenciales de la URL: http://user:pass@host:port
            auth_match = re.match(r"http://(.+):(.+)@(.+):(\d+)", proxy_url)
            if auth_match:
                user, pw, host, port = auth_match.groups()
                
                # Creamos el plugin de Chrome al vuelo
                plugin_file = '/tmp/proxy_auth_plugin.zip'
                manifest_json = """
                {
                    "version": "1.0.0",
                    "manifest_version": 2,
                    "name": "Chrome Proxy",
                    "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
                    "background": { "scripts": ["background.js"] },
                    "minimum_chrome_version":"22.0.0"
                }
                """
                background_js = """
                var config = {
                    mode: "fixed_servers",
                    rules: {
                        singleProxy: { scheme: "http", host: "%s", port: parseInt(%s) },
                        bypassList: []
                    }
                };
                chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
                chrome.webRequest.onAuthRequired.addListener(
                    function(details) {
                        return { authCredentials: { username: "%s", password: "%s" } };
                    },
                    {urls: ["<all_urls>"]}, ["blocking"]
                );
                """ % (host, port, user, pw)

                with zipfile.ZipFile(plugin_file, 'w') as zp:
                    zp.writestr("manifest.json", manifest_json)
                    zp.writestr("background.js", background_js)
                
                options.add_extension(plugin_file)

        remote_url = os.getenv('SELENIUM_URL', 'http://chrome:4444/wd/hub')

        # Inicialización estándar de Selenium (Sin fallos de compatibilidad)
        driver = webdriver.Remote(
            command_executor=remote_url,
            options=options
        )

        return cls(driver=driver, default_timeout=timeout)

    # --- Métodos de utilidad (se mantienen igual) ---
    def slow_type(self, element: WebElement, text: str, delay_range: Tuple[float, float] = (0.05, 0.15)):
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(*delay_range))

    def wait_for_present(self, locator: Locator, timeout: Optional[int] = None) -> Optional[WebElement]:
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        try:
            return wait.until(EC.presence_of_element_located(locator))
        except TimeoutException:
            return None

    def wait_for_clickable(self, locator: Locator, timeout: Optional[int] = None) -> Optional[WebElement]:
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        try:
            return wait.until(EC.element_to_be_clickable(locator))
        except TimeoutException:
            return None

    def wait_for_visible(self, locator: Locator, timeout: Optional[int] = None) -> Optional[WebElement]:
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        try:
            return wait.until(EC.visibility_of_element_located(locator))
        except TimeoutException:
            return None

    def get_all_objects(self, locator: Locator, timeout: Optional[int] = None) -> List[WebElement]:
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        try:
            wait.until(EC.presence_of_all_elements_located(locator))
            return self.driver.find_elements(*locator)
        except TimeoutException:
            return []

    def human_jitter(self, min_s: float = 1.0, max_s: float = 3.5):
        time.sleep(random.uniform(min_s, max_s))

    def quit(self):
        if self.driver:
            self.driver.quit()
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from playwright_stealth import Stealth


class BaseScraper:
    # Cohesive browser profile optimized for standard localized tracking
    PROFILE = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "platform": "Win32",
        "locale": "es-MX",  # Matches Mexican IP localization
        "timezone_id": "America/Mexico_City",  # Matches Mexican IP timezone
    }

    def __init__(
        self,
        headless=True,
        use_proxy=False,
        proxy_user=None,
        proxy_pass=None,
        proxy_server=None,
        remote_url=None,
    ):
        self.headless = headless
        self.use_proxy = use_proxy
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass
        self.proxy_server = proxy_server
        self.remote_url = remote_url

        self.playwright_manager = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _generate_decodo_url(self):
        ports = [
            "20001",
            "20002",
            "20003",
            "20004",
            "20005",
            "20006",
            "20007",
            "20008",
            "20009",
            "20010",
        ]
        port = random.choice(ports)
        url = self.proxy_server + ":" + port
        return url

    async def start(self):
        """Launches the browser engine and applies strict data-saving protocols."""
        # Async Playwright instantiation
        self.playwright_manager = async_playwright()
        self.playwright = await self.playwright_manager.start()

        # 1. Build Targeted Decodo Proxy Configuration
        proxy_config = None
        if self.use_proxy:
            if not self.proxy_user or not self.proxy_pass:
                raise ValueError(
                    "Proxy is enabled but Decodo credentials were not provided."
                )

            # Stick to a single IP during this session to avoid wasting authentication bandwidth
            session_id = f"mx_sess_{random.randint(10000, 99999)}"

            # CRITICAL: Appending '-country-mx' forces Decodo to pull from Mexican residential pools.
            # Appending '-session-' preserves the IP context so you don't burn data switching nodes constantly.
            targeted_username = f"{self.proxy_user}-country-mx-session-{session_id}"

            print(
                f"Configuring Decodo proxy: Targeting Mexico (MX) Residential Node..."
            )
            proxy_config = {
                "server": self._generate_decodo_url(),
                "username": targeted_username,
                "password": self.proxy_pass,
            }

        # 2. Setup Driver Connection
        if self.remote_url:
            cdp_url = self.remote_url.replace("/wd/hub", "")
            print(f"Connecting to remote VNC container via CDP: {cdp_url}")
            try:
                self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                if not self.headless:
                    raise e
                print(
                    f"Failed to connect to remote Chrome: {e}. Falling back to local launch..."
                )
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
        else:
            print("Launching local headless execution...")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

        # 3. Create Context with Unified Mexican Metadata
        context_kwargs = {
            "viewport": self.PROFILE["viewport"],
            "user_agent": self.PROFILE["user_agent"],
            "locale": self.PROFILE["locale"],
            "timezone_id": self.PROFILE["timezone_id"],
        }
        if proxy_config:
            context_kwargs["proxy"] = proxy_config

        self.context = await self.browser.new_context(**context_kwargs)

        # Inject platform fingerprint overwrite
        await self.context.add_init_script(
            f"Object.defineProperty(navigator, 'platform', {{get: () => '{self.PROFILE['platform']}'}});"
        )

        self.page = await self.context.new_page()

        # --- NEW V2.0+ STEALTH IMPLEMENTATION ---
        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)

        # 4. CRITICAL DATA SAVER: Intercept & Abort Heavy Resource Requests
        # This single block prevents images, stylesheets, and fonts from transferring over your paid proxy.
        async def block_heavy_resources(route):
            allowed_types = ["document", "script", "xhr", "fetch"]
            if route.request.resource_type not in allowed_types:
                # Silently drop images, videos, stylesheets, fonts, and trackers
                await route.abort()
            else:
                await route.continue_()

        await self.page.route("**/*", block_heavy_resources)

        print("Scraper successfully started with data-saving routing rules.")
        return self.page

    async def stop(self):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except (PlaywrightError, Exception):
            # If the browser is already closed, we don't care about the error during cleanup
            pass
        finally:
            if self.playwright_manager:
                # Safely exit the async context manager
                try:
                    await self.playwright_manager.__aexit__()
                except:
                    pass
        print("Scraper safely closed.")

    async def human_type(self, locator, text, min_delay=50, max_delay=150):
        try:
            await locator.focus()
            for char in text:
                await locator.press_sequentially(char)
                if random.random() < 0.10:
                    await self.page.wait_for_timeout(random.uniform(300, 600))
                else:
                    await self.page.wait_for_timeout(random.uniform(min_delay, max_delay))
        except PlaywrightError:
            print("Browser closed while typing.")

    async def human_jitter_click(self, element, clicks=1):
        """
        Moves the mouse to the DOM element object with human-like jitter, then clicks.

        :param element: The Playwright ElementHandle object to click.
        :param clicks: Number of times to click (default 1).
        """
        try:
            # 1. Bring the element into view and pause (humans read the screen after scrolling)
            await element.scroll_into_view_if_needed()
            await self.page.wait_for_timeout(random.randint(300, 700))

            # 2. Extract the exact screen coordinates of the element object
            box = await element.bounding_box()
            if not box:
                # Fallback if the element exists but is mathematically 0x0 or obscured
                print("Warning: Could not get bounding box. Falling back to strict click.")
                await element.click(click_count=clicks)
                return

            # 3. Define a safe clicking zone (avoid extreme edges)
            # We target the inner 80% of the element's width and height
            start_x = box["x"] + (box["width"] * 0.1)
            end_x = box["x"] + (box["width"] * 0.9)
            start_y = box["y"] + (box["height"] * 0.1)
            end_y = box["y"] + (box["height"] * 0.9)

            # Pick a randomized point inside that safe zone
            target_x = random.uniform(start_x, end_x)
            target_y = random.uniform(start_y, end_y)

            # 4. Phase 1: The Overshoot (Jitter)
            # Simulate a human swiping the mouse toward the button but missing slightly
            jitter_x = target_x + random.uniform(-40, 40)
            jitter_y = target_y + random.uniform(-20, 20)

            # Move to the jitter point. The 'steps' parameter breaks the movement
            # into multiple micro-events so it doesn't happen instantly.
            await self.page.mouse.move(jitter_x, jitter_y, steps=random.randint(5, 12))

            # Micro-pause as the human realizes they aren't on the button yet
            await self.page.wait_for_timeout(random.randint(50, 150))

            # 5. Phase 2: The Correction
            # Move to the actual target coordinates
            await self.page.mouse.move(target_x, target_y, steps=random.randint(3, 8))

            # Hover pause before committing to the click
            await self.page.wait_for_timeout(random.randint(100, 300))

            # 6. Execute the click at the specific, non-centered X/Y coordinates
            await self.page.mouse.click(target_x, target_y, click_count=clicks)
        except PlaywrightError:
            print("Browser closed while performing jitter click.")

    async def human_pause(self):
        """Pauses execution randomly between 1 and 3 seconds."""
        # Pick a random float between 1000ms (1s) and 3000ms (3s)
        actual_wait = random.uniform(1000, 3000)
        try:
            await self.page.wait_for_timeout(actual_wait)
        except PlaywrightError:
            print("Browser closed during pause.")

    async def wait_for_page_load(self):
        try:
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except (PlaywrightTimeoutError, PlaywrightError):
            print("Network did not idle or target closed, proceeding...")

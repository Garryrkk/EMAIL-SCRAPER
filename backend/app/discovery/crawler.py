import logging
import aiohttp
import asyncio
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiter per domain
_domain_rate_limiters = {}

# Global semaphore to limit concurrent crawlers per domain
_global_domain_semaphores = {}
_semaphore_lock = asyncio.Lock()


class DomainRateLimiter:
    """Rate limiter per domain."""
    
    def __init__(self, requests_per_second: int = 2):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
        self.lock = asyncio.Lock()
    
    async def wait(self):
        """Wait if needed to respect rate limit."""
        async with self.lock:
            elapsed = time.time() - self.last_request_time
            wait_time = (1.0 / self.requests_per_second) - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()


class WebCrawler:
    """Web crawler for discovering company information."""

    def __init__(self, use_js_rendering: bool = False):
        self.session = None
        self.user_agent = settings.CRAWLER_USER_AGENT
        self.timeout = aiohttp.ClientTimeout(total=settings.CRAWLER_TIMEOUT)
        self.use_js_rendering = use_js_rendering
        self.browser = None
        self.playwright = None

    async def initialize(self):
        """Initialize HTTP session and optionally Playwright for JS rendering."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Optional: Initialize Playwright for JS-heavy sites
        if self.use_js_rendering:
            try:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
                logger.info("Playwright browser initialized for JS rendering")
            except ImportError:
                logger.warning("Playwright not installed. JS rendering disabled. Install with: pip install playwright")
                self.use_js_rendering = False
            except Exception as e:
                logger.error(f"Failed to initialize Playwright: {e}")
                self.use_js_rendering = False

    async def close(self):
        """Close HTTP session and Playwright browser."""
        if self.session:
            await self.session.close()
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()

    async def _get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or create semaphore for domain to limit concurrent requests."""
        async with _semaphore_lock:
            if domain not in _global_domain_semaphores:
                # Limit to 3 concurrent requests per domain across all crawler instances
                _global_domain_semaphores[domain] = asyncio.Semaphore(3)
            return _global_domain_semaphores[domain]

    async def fetch_page(self, url: str) -> tuple[str, str]:
        """Fetch page content.
        
        Returns:
            tuple: (content, failure_reason) where failure_reason is one of:
                   None (success), "robots", "timeout", "error"
        """
        try:
            domain = urlparse(url).netloc
            
            # Get domain semaphore for concurrency control
            semaphore = await self._get_domain_semaphore(domain)
            
            async with semaphore:
                # Rate limiting
                if domain not in _domain_rate_limiters:
                    _domain_rate_limiters[domain] = DomainRateLimiter(
                        requests_per_second=settings.CRAWLER_RATE_LIMIT_PER_DOMAIN
                    )
                
                limiter = _domain_rate_limiters[domain]
                await limiter.wait()

                # Check robots.txt (strict compliance mode)
                robots_allowed = await self._check_robots_txt(url)
                if not robots_allowed:
                    logger.warning(f"URL blocked by robots.txt: {url}")
                    return None, "robots"

                # Try JS rendering first if enabled, fallback to static HTML
                if self.use_js_rendering and self.browser:
                    content = await self._fetch_with_js(url)
                    if content:
                        return content, None
                
                # Fallback to static HTML fetch
                return await self._fetch_static(url)

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None, "error"

    async def _fetch_static(self, url: str) -> tuple[str, str]:
        """Fetch static HTML content."""
        headers = {"User-Agent": self.user_agent}
        
        for attempt in range(settings.CRAWLER_MAX_RETRIES):
            try:
                async with self.session.get(
                    url,
                    headers=headers,
                    ssl=False,
                    allow_redirects=True,
                ) as response:
                    if response.status == 200:
                        return await response.text(), None
                    elif response.status in [429, 503]:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                    else:
                        return None, "error"
            except asyncio.TimeoutError:
                if attempt == settings.CRAWLER_MAX_RETRIES - 1:
                    logger.error(f"Timeout fetching {url}")
                    return None, "timeout"
                await asyncio.sleep(1)

        return None, "error"

    async def _fetch_with_js(self, url: str) -> str:
        """Fetch page content with JavaScript rendering using Playwright."""
        try:
            page = await self.browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=settings.CRAWLER_TIMEOUT * 1000)
            content = await page.content()
            await page.close()
            return content
        except Exception as e:
            logger.warning(f"JS rendering failed for {url}: {e}")
            return None

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt (strict compliance)."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)
            
            async with self.session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    # FIX 3: Use parse() with splitlines() instead of read_file()
                    rp.parse((await resp.text()).splitlines())
                elif resp.status == 404:
                    # No robots.txt means all pages allowed
                    return True
                else:
                    # Other errors: fail open (assume allowed)
                    logger.warning(f"Could not fetch robots.txt for {domain} (status {resp.status})")
                    return True

            return rp.can_fetch(self.user_agent, url)
        except Exception as e:
            # Fail open: if we can't check robots.txt, assume allowed
            logger.debug(f"Error checking robots.txt for {url}: {e}")
            return True

    async def crawl_domain(self, domain: str) -> dict:
        """Crawl company domain for pages."""
        # FIX 2: Add HTTP fallback for sites that don't support HTTPS
        urls = [
            f"https://{domain}",
            f"http://{domain}",
            f"https://{domain}/about",
            f"http://{domain}/about",
            f"https://{domain}/about-us",
            f"http://{domain}/about-us",
            f"https://{domain}/team",
            f"http://{domain}/team",
            f"https://{domain}/contact",
            f"http://{domain}/contact",
            f"https://{domain}/contact-us",
            f"http://{domain}/contact-us",
        ]

        pages = []
        blocked_count = 0
        timeout_count = 0
        error_count = 0
        
        for url in urls:
            content, reason = await self.fetch_page(url)
            if content:
                pages.append({
                    "url": url,
                    "content": content,
                })
            elif reason == "robots":
                blocked_count += 1
            elif reason == "timeout":
                timeout_count += 1
            elif reason == "error":
                error_count += 1

        # FIX 1: Return crawl metadata to differentiate failure from no content
        crawl_status = "success"
        if not pages:
            if blocked_count > 0:
                crawl_status = "blocked"
            elif timeout_count > 0:
                crawl_status = "failed"
            else:
                crawl_status = "no_content"
        elif len(pages) < len(urls) // 3:
            crawl_status = "partial"
        
        return {
            "pages": pages,
            "crawl_status": crawl_status,
            "total_attempted": len(urls),
            "successful": len(pages),
            "blocked": blocked_count,
            "timeouts": timeout_count,
            "errors": error_count,
        }
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

    def __init__(self):
        self.session = None
        self.user_agent = settings.CRAWLER_USER_AGENT
        self.timeout = aiohttp.ClientTimeout(total=settings.CRAWLER_TIMEOUT)

    async def initialize(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> str:
        """Fetch page content."""
        try:
            domain = urlparse(url).netloc
            
            # Rate limiting
            if domain not in _domain_rate_limiters:
                _domain_rate_limiters[domain] = DomainRateLimiter(
                    requests_per_second=settings.CRAWLER_RATE_LIMIT_PER_DOMAIN
                )
            
            limiter = _domain_rate_limiters[domain]
            await limiter.wait()

            # Check robots.txt
            if not await self._check_robots_txt(url):
                logger.warning(f"URL blocked by robots.txt: {url}")
                return None

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
                            return await response.text()
                        elif response.status in [429, 503]:
                            wait_time = 2 ** attempt
                            await asyncio.sleep(wait_time)
                        else:
                            return None
                except asyncio.TimeoutError:
                    if attempt == settings.CRAWLER_MAX_RETRIES - 1:
                        logger.error(f"Timeout fetching {url}")
                        return None
                    await asyncio.sleep(1)

            return None

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)
            
            async with self.session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    rp.read_file(await resp.text())
                else:
                    return True  # Assume allowed if no robots.txt

            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True  # Fail open

    async def crawl_domain(self, domain: str) -> list:
        """Crawl company domain for pages."""
        urls = [
            f"https://{domain}",
            f"https://{domain}/about",
            f"https://{domain}/about-us",
            f"https://{domain}/team",
            f"https://{domain}/contact",
            f"https://{domain}/contact-us",
        ]

        pages = []
        for url in urls:
            content = await self.fetch_page(url)
            if content:
                pages.append({
                    "url": url,
                    "content": content,
                })

        return pages
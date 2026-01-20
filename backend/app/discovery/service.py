import logging
import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup
import aiohttp
from urllib.parse import urljoin, urlparse
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

CRAWL_PATHS = [
    "/",
    "/contact", "/contact-us",
    "/about", "/about-us",
    "/team",
    "/careers", "/jobs",
    "/press",
    "/footer",
]

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "protonmail.com", "icloud.com", "mail.com",
}


class DiscoveredEmail:
    """Represents a discovered email with metadata."""
    
    def __init__(self, email: str, source: str, url: str, count: int = 1, email_type: str = "work"):
        self.email = email.lower()
        self.domain = email.split("@")[1].lower()
        self.source = source
        self.url = url
        self.occurrences = count
        self.email_type = email_type  # "work" or "personal"
        self.confidence_boost = 0.0
    
    def to_dict(self):
        return {
            "email": self.email,
            "domain": self.domain,
            "source": self.source,
            "url": self.url,
            "occurrences": self.occurrences,
            "email_type": self.email_type,
        }


class PublicDiscoveryEngine:
    """
    Crawls company websites and discovers emails.
    
    NEW: Now handles both work emails AND personal emails (Gmail, etc.)
    - Work emails: Company domain emails (highest priority, used for patterns)
    - Personal emails: Gmail, Yahoo, etc. (useful for founder contacts)
    """

    def __init__(self, domain: str):
        self.domain = domain
        self.base_url = f"https://{domain}"
        self.session = None
        self.discovered_emails: Dict[str, DiscoveredEmail] = {}
        self.failed_urls = []

    async def initialize(self):
        """Start HTTP session."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.CRAWLER_TIMEOUT)
        )

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()

    async def discover(self) -> Dict:
        """
        Main discovery pipeline.
        
        Returns:
            {
                "work_emails": [...],      # Company domain emails
                "personal_emails": [...],  # Gmail, Yahoo, etc.
            }
        """
        if not self.session:
            await self.initialize()

        try:
            await self._crawl_all_pages()
            await self._filter_discovered_emails()

            # Separate into work and personal
            work_emails = []
            personal_emails = []

            for email, data in self.discovered_emails.items():
                email_dict = data.to_dict()
                
                if data.email_type == "work":
                    work_emails.append(email_dict)
                else:
                    personal_emails.append(email_dict)

            # Sort by occurrences
            work_emails = sorted(work_emails, key=lambda x: x["occurrences"], reverse=True)
            personal_emails = sorted(personal_emails, key=lambda x: x["occurrences"], reverse=True)

            logger.info(
                f"Discovery complete for {self.domain}: "
                f"{len(work_emails)} work emails, {len(personal_emails)} personal emails"
            )

            return {
                "work_emails": work_emails,
                "personal_emails": personal_emails,
            }

        except Exception as e:
            logger.error(f"Discovery error for {self.domain}: {e}")
            return {"work_emails": [], "personal_emails": []}

    async def _crawl_all_pages(self):
        """Crawl all important pages and extract emails."""
        tasks = []
        
        for path in CRAWL_PATHS:
            url = urljoin(self.base_url, path)
            tasks.append(self._crawl_page(url))

        for coro in asyncio.as_completed(tasks):
            await coro

    async def _crawl_page(self, url: str):
        """Crawl single page and extract emails."""
        try:
            logger.debug(f"Crawling: {url}")

            async with self.session.get(url, ssl=False, allow_redirects=True) as response:
                if response.status != 200:
                    self.failed_urls.append(url)
                    return

                html = await response.text()
                await self._extract_from_html(html, url)

        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
            self.failed_urls.append(url)
        except Exception as e:
            logger.debug(f"Error crawling {url}: {e}")
            self.failed_urls.append(url)

    async def _extract_from_html(self, html: str, page_url: str):
        """Extract emails from HTML with context."""
        soup = BeautifulSoup(html, 'html.parser')

        for script in soup(['script', 'style']):
            script.decompose()

        # 1. mailto: links (HIGHEST confidence)
        for link in soup.find_all('a', href=re.compile(r'^mailto:')):
            email = link.get('href', '').replace('mailto:', '').split('?')[0].strip()
            if self._is_valid_email(email):
                email_type = self._determine_email_type(email)
                self._add_email(
                    email,
                    source="mailto_link",
                    url=page_url,
                    boost=0.20,
                    email_type=email_type,
                )

        # 2. Footer content
        footer = soup.find('footer')
        if footer:
            text = footer.get_text()
            emails = EMAIL_REGEX.findall(text)
            for email in emails:
                if self._is_valid_email(email):
                    email_type = self._determine_email_type(email)
                    self._add_email(
                        email,
                        source="footer_text",
                        url=page_url,
                        boost=0.15,
                        email_type=email_type,
                    )

        # 3. Contact/Careers pages
        if any(x in page_url for x in ['contact', 'careers', 'about']):
            text = soup.get_text()
            emails = EMAIL_REGEX.findall(text)
            for email in emails:
                if self._is_valid_email(email):
                    email_type = self._determine_email_type(email)
                    self._add_email(
                        email,
                        source="contact_page",
                        url=page_url,
                        boost=0.10,
                        email_type=email_type,
                    )

        # 4. Schema.org
        await self._extract_schema_org(soup, page_url)

    async def _extract_schema_org(self, soup: BeautifulSoup, page_url: str):
        """Extract from structured data."""
        import json
        
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                self._parse_schema_recursive(data, page_url, boost=0.12)
            except Exception as e:
                logger.debug(f"Schema parse error: {e}")

    def _parse_schema_recursive(self, data, page_url: str, boost: float, depth=0):
        """Recursively parse schema data."""
        if depth > 5:
            return

        if isinstance(data, dict):
            for key in ['email', 'contactPoint', 'url']:
                if key in data:
                    value = data[key]
                    if isinstance(value, str) and '@' in value:
                        if self._is_valid_email(value):
                            email_type = self._determine_email_type(value)
                            self._add_email(value, "schema_org", page_url, boost, email_type)
                    elif isinstance(value, dict):
                        self._parse_schema_recursive(value, page_url, boost, depth + 1)

            for value in data.values():
                if isinstance(value, (dict, list)):
                    self._parse_schema_recursive(value, page_url, boost, depth + 1)

        elif isinstance(data, list):
            for item in data:
                self._parse_schema_recursive(item, page_url, boost, depth + 1)

    def _add_email(
        self,
        email: str,
        source: str,
        url: str,
        boost: float = 0.0,
        email_type: str = "work",
    ):
        """Add discovered email with deduplication."""
        email_lower = email.lower()
        
        if email_lower in self.discovered_emails:
            self.discovered_emails[email_lower].occurrences += 1
        else:
            disc_email = DiscoveredEmail(email, source, url, email_type=email_type)
            disc_email.confidence_boost = boost
            self.discovered_emails[email_lower] = disc_email

    def _determine_email_type(self, email: str) -> str:
        """Determine if email is work or personal."""
        domain = email.split("@")[1].lower()
        
        if domain in GENERIC_DOMAINS:
            return "personal"
        elif domain == self.domain or domain.endswith(f".{self.domain}"):
            return "work"
        else:
            return "personal"

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        if not email or '@' not in email:
            return False

        email = email.lower().strip()
        
        # Skip abuse patterns
        if email.startswith(('noreply', 'no-reply', 'donotreply')):
            return False

        return True

    async def _filter_discovered_emails(self):
        """Remove noise from discovered emails."""
        filtered = {}
        
        for email, data in self.discovered_emails.items():
            # Always keep mailto: links
            if data.source == "mailto_link":
                filtered[email] = data
            # Keep if appears 2+ times
            elif data.occurrences >= 2:
                filtered[email] = data
            # Keep strong source signals
            elif data.source in ["footer_text", "schema_org"]:
                filtered[email] = data
            # For personal emails: keep if found on prominent page
            elif data.email_type == "personal" and data.source in ["contact_page", "mailto_link"]:
                filtered[email] = data

        self.discovered_emails = filtered
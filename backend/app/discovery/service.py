import logging
import re
import random
from typing import List, Dict, Set
from bs4 import BeautifulSoup
import aiohttp
import httpx
from urllib.parse import urljoin, urlparse
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

# Standard email regex
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Obfuscated email patterns (e.g., "info [at] company [dot] com")
OBFUSCATED_PATTERNS = [
    (r'\b([A-Za-z0-9._%+-]+)\s*\[\s*at\s*\]\s*([A-Za-z0-9.-]+)\s*\[\s*dot\s*\]\s*([A-Za-z]{2,})\b', r'\1@\2.\3'),
    (r'\b([A-Za-z0-9._%+-]+)\s*\(\s*at\s*\)\s*([A-Za-z0-9.-]+)\s*\(\s*dot\s*\)\s*([A-Za-z]{2,})\b', r'\1@\2.\3'),
    (r'\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)\s+dot\s+([A-Za-z]{2,})\b', r'\1@\2.\3'),
]

CRAWL_PATHS = [
    "/",
    "/contact", "/contact-us", "/contactus", "/get-in-touch", "/reach-us",
    "/about", "/about-us", "/aboutus", "/who-we-are", "/company",
    "/team", "/our-team", "/leadership", "/people", "/management",
    "/careers", "/jobs", "/work-with-us", "/join-us", "/hiring",
    "/press", "/media", "/news", "/newsroom", "/press-room",
    "/support", "/help", "/customer-service", "/customer-support",
    "/privacy", "/legal", "/terms", "/tos", "/privacy-policy",
    "/footer", "/sitemap",
    "/investors", "/investor-relations",
    "/partners", "/partnership",
    "/sales", "/pricing", "/enterprise",
]

# Common email prefixes to generate when no emails found
COMMON_EMAIL_PREFIXES = [
    "info", "contact", "hello", "support", "sales", "help",
    "admin", "team", "hr", "careers", "press", "media",
    "marketing", "partnerships", "business", "enquiries", "inquiries"
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
        self.crawled_urls = set()  # Track what we've already crawled

    async def initialize(self):
        """Start HTTP session with browser-like headers."""
        import random
        
        # Multiple User-Agents to rotate
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        
        self.user_agents = user_agents
        self.current_ua = random.choice(user_agents)
        
        headers = {
            "User-Agent": self.current_ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Create connector with less aggressive settings
        connector = aiohttp.TCPConnector(
            limit=5,  # Limit concurrent connections
            limit_per_host=2,  # Limit per host
            ssl=False,
        )
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45),  # Increased timeout
            headers=headers,
            connector=connector,
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

            # If no work emails found, generate common patterns
            if not work_emails:
                generated = await self._generate_common_emails()
                for email_dict in generated:
                    work_emails.append(email_dict)

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

    async def _generate_common_emails(self) -> List[Dict]:
        """Generate common email patterns when no emails are discovered."""
        generated = []
        
        # Only generate for the top common prefixes
        top_prefixes = ["info", "contact", "hello", "support", "sales", "team"]
        
        for prefix in top_prefixes:
            email = f"{prefix}@{self.domain}"
            generated.append({
                "email": email,
                "domain": self.domain,
                "source": "generated",
                "url": f"https://{self.domain}",
                "occurrences": 1,
                "email_type": "work",
            })
        
        logger.info(f"Generated {len(generated)} common email patterns for {self.domain}")
        return generated

    async def _crawl_all_pages(self):
        """Crawl all important pages and extract emails."""
        # Try HTTPS first, then HTTP fallback
        base_urls = [f"https://{self.domain}", f"http://{self.domain}"]
        
        for base in base_urls:
            self.base_url = base
            
            # Use semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
            
            async def limited_crawl(url):
                async with semaphore:
                    await self._crawl_page(url)
                    await asyncio.sleep(random.uniform(0.1, 0.3))  # Small delay
            
            # Create tasks for all paths
            tasks = []
            for path in CRAWL_PATHS:
                url = urljoin(base, path)
                if url not in self.crawled_urls:
                    self.crawled_urls.add(url)
                    tasks.append(limited_crawl(url))
            
            # Run all tasks concurrently with semaphore limiting
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # If we got any emails with HTTPS, don't try HTTP
            if self.discovered_emails:
                break

    async def _crawl_page(self, url: str):
        """Crawl single page and extract emails."""
        try:
            logger.info(f"Crawling: {url}")
            
            # Rotate User-Agent per request
            headers = {"User-Agent": random.choice(self.user_agents)}
            # Add referer to look more legitimate
            if hasattr(self, 'last_url') and self.last_url:
                headers["Referer"] = self.last_url
            
            async with self.session.get(url, ssl=False, allow_redirects=True, headers=headers) as response:
                logger.info(f"Response from {url}: status={response.status}")
                
                # Handle redirects to other domains (CDN, etc.)
                if response.status in (301, 302, 303, 307, 308):
                    logger.info(f"Redirect from {url}")
                
                if response.status == 403:
                    # Try with different headers
                    logger.warning(f"403 Forbidden for {url} - trying with HTTPX fallback")
                    await self._crawl_page_minimal(url)
                    return
                
                if response.status != 200:
                    logger.warning(f"Non-200 status for {url}: {response.status}")
                    self.failed_urls.append(url)
                    return

                html = await response.text()
                logger.info(f"Got {len(html)} bytes from {url}")
                await self._extract_from_html(html, url)
                
                self.last_url = url  # Track for referer
                
                # Also look for additional internal links with contact/email keywords
                await self._find_contact_links(html, url)

        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
            self.failed_urls.append(url)
        except aiohttp.ClientError as e:
            logger.warning(f"Client error crawling {url}: {e}")
            self.failed_urls.append(url)
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            self.failed_urls.append(url)

    async def _crawl_page_minimal(self, url: str):
        """Fallback crawler with minimal headers for sites that block browser-like requests."""
        try:
            # Try httpx as it handles some sites better than aiohttp
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=False,  # Skip SSL verification
                http2=True,  # Enable HTTP/2
            ) as client:
                # Try with Chrome-like headers
                headers = {
                    "User-Agent": random.choice(self.user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    html = response.text
                    logger.info(f"HTTPX success for {url}: {len(html)} bytes")
                    await self._extract_from_html(html, url)
                    return
                
                # Try with Googlebot
                headers["User-Agent"] = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    html = response.text
                    logger.info(f"HTTPX Googlebot success for {url}: {len(html)} bytes")
                    await self._extract_from_html(html, url)
                    return
                    
                logger.warning(f"All HTTPX attempts failed for {url}: {response.status_code}")
                self.failed_urls.append(url)
                
        except Exception as e:
            logger.warning(f"HTTPX crawl failed for {url}: {e}")
            self.failed_urls.append(url)

    async def _find_contact_links(self, html: str, base_url: str):
        """Find and crawl additional contact-related links (limited to avoid slowdown)."""
        soup = BeautifulSoup(html, 'html.parser')
        contact_keywords = ['contact', 'email', 'reach', 'support', 'help']
        
        found_links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            link_text = link.get_text().lower()
            
            # Check if link URL or text contains contact keywords
            if any(kw in href.lower() or kw in link_text for kw in contact_keywords):
                full_url = urljoin(base_url, href)
                
                # Only crawl same-domain links we haven't visited
                if self.domain in full_url and full_url not in self.crawled_urls:
                    found_links.append(full_url)
                    self.crawled_urls.add(full_url)
        
        # Crawl up to 3 additional contact links in parallel
        tasks = []
        for url in found_links[:3]:
            tasks.append(self._crawl_page(url))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _extract_from_html(self, html: str, page_url: str):
        """Extract emails from HTML with context."""
        soup = BeautifulSoup(html, 'html.parser')

        for script in soup(['script', 'style']):
            script.decompose()

        # First, try to find ALL emails in the page text
        page_text = soup.get_text()
        all_emails = EMAIL_REGEX.findall(page_text)
        logger.info(f"Found {len(all_emails)} potential emails in {page_url}: {all_emails[:5]}")

        # 1. mailto: links (HIGHEST confidence)
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.IGNORECASE))
        logger.info(f"Found {len(mailto_links)} mailto links in {page_url}")
        
        for link in mailto_links:
            email = link.get('href', '').replace('mailto:', '').split('?')[0].strip()
            logger.info(f"Mailto email found: {email}")
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

        # 5. Fallback: Extract ALL emails from page text
        # This catches emails that aren't in mailto links, footer, or special pages
        for email in all_emails:
            if self._is_valid_email(email):
                email_type = self._determine_email_type(email)
                self._add_email(
                    email,
                    source="page_text",
                    url=page_url,
                    boost=0.05,
                    email_type=email_type,
                )

        # 6. Extract from raw HTML (emails in data attributes, hidden elements, etc.)
        raw_html_emails = EMAIL_REGEX.findall(html)
        for email in raw_html_emails:
            if self._is_valid_email(email):
                email_type = self._determine_email_type(email)
                self._add_email(
                    email,
                    source="raw_html",
                    url=page_url,
                    boost=0.03,
                    email_type=email_type,
                )

        # 7. Try to find obfuscated emails (e.g., "info [at] company [dot] com")
        for pattern, replacement in OBFUSCATED_PATTERNS:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    email = f"{match[0]}@{match[1]}.{match[2]}"
                else:
                    email = re.sub(pattern, replacement, match, flags=re.IGNORECASE)
                
                if self._is_valid_email(email):
                    email_type = self._determine_email_type(email)
                    self._add_email(
                        email,
                        source="obfuscated",
                        url=page_url,
                        boost=0.08,
                        email_type=email_type,
                    )

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
        
        # Must have exactly one @ sign
        if email.count('@') != 1:
            return False
        
        local, domain = email.split('@')
        
        # Check for image/asset file extensions in domain
        if any(domain.endswith(x) for x in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.ico']):
            return False
        
        # Domain must have at least one dot
        if '.' not in domain:
            return False
        
        # Domain should have reasonable length
        if len(domain) < 3 or len(domain) > 255:
            return False
        
        # Local part should have reasonable length
        if len(local) < 1 or len(local) > 64:
            return False
        
        # Skip abuse patterns
        if local.startswith(('noreply', 'no-reply', 'donotreply')):
            return False
        
        # Skip obvious fake domains
        fake_domains = ['example.com', 'test.com', 'domain.com', 'yourcompany.com', 
                        'yourdomain.com', 'email.com', 'company.com', 'beispiel.de',
                        'example.org', 'acme.com', 'placeholder.com', 'mailinator.com',
                        'guerrillamail.com', 'temp-mail.org', 'throwaway.email']
        if domain in fake_domains:
            return False
        
        # Skip if domain looks like a filename
        if any(x in domain for x in ['@2x', '@3x', '_icon', '_image']):
            return False
        
        # Validate TLD (top-level domain) - must be valid
        tld = domain.split('.')[-1]
        # TLD should be 2-6 characters (e.g., com, org, io, co.uk becomes uk)
        if len(tld) < 2 or len(tld) > 10:
            return False
        # TLD should be all letters
        if not tld.isalpha():
            return False
        # Check for suspicious TLDs that indicate bad parsing
        invalid_tlds = ['if', 'then', 'else', 'for', 'while', 'var', 'let', 'const', 'function']
        if tld in invalid_tlds:
            return False
        
        # Check for common valid TLDs - reject weird ones
        common_tlds = ['com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'me', 'info', 'biz', 
                       'us', 'uk', 'de', 'fr', 'in', 'au', 'ca', 'jp', 'cn', 'ru', 'br',
                       'it', 'es', 'nl', 'se', 'ch', 'pl', 'be', 'at', 'ie', 'nz', 'mx',
                       'app', 'dev', 'tech', 'ai', 'cloud', 'online', 'shop', 'store', 'blog',
                       'xyz', 'site', 'so', 'tv', 'fm', 'gg', 'cc', 'ly']
        # If TLD is > 4 chars and not in common list, it might be bad parsing
        if len(tld) > 4 and tld not in common_tlds:
            return False
        
        # Check for domains that run together (e.g., gmail.comajmer)
        # Common domains should end cleanly
        common_email_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        for cd in common_email_domains:
            if cd in domain and domain != cd and not domain.endswith('.' + cd):
                # Domain contains gmail.com but doesn't end with it - bad parsing
                return False

        return True

    async def _filter_discovered_emails(self):
        """Remove noise from discovered emails - LESS AGGRESSIVE filtering."""
        filtered = {}
        
        for email, data in self.discovered_emails.items():
            # Skip obvious fake/example emails
            if any(x in email for x in ['example.com', 'test.com', 'domain.com', 'yourcompany.com', 'yourdomain.com', 'email.com', 'company.com']):
                continue
            # Skip image file extensions mistakenly captured
            if any(email.endswith(x) for x in ['.png', '.jpg', '.gif', '.svg', '.webp', '.css', '.js']):
                continue
            # Keep ALL emails found - be aggressive in discovery
            filtered[email] = data

        self.discovered_emails = filtered
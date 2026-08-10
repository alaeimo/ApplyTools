import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set

from apps.websites.models import Website
from apps.positions.models import Position


class PositionLinkExtractor:
    """
    Service to extract position links from paginated listing pages.
    """
    
    def __init__(self, website: Website):
        """
        Initialize the link extractor with a website configuration.
        
        Args:
            website: Website configuration object
        """
        self.website = website
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': website.user_agent,
        })
        self.timeout = website.request_timeout
        self.delay = website.request_delay
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a URL and return BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup: Parsed HTML or None if error
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            time.sleep(self.delay)
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_links_from_page(self, page_number: int) -> List[Dict]:
        """
        Extract position data using hierarchical selectors.
        
        Args:
            page_number: Page number to extract from
            
        Returns:
            List[Dict]: List of dicts with 'url', 'title', 'company'
        """
        url = self.website.get_pagination_url(page_number)
        soup = self._fetch_page(url)
        
        if not soup:
            return []
        
        # Level 1: Find all position containers
        position_items = soup.select(self.website.listing_item_selector)
        
        results = []
        for item in position_items:
            # Level 2: Extract link (required)
            link_element = item.select_one(self.website.position_link_selector)
            if not link_element:
                continue
            
            href = link_element.get('href')
            if not href:
                continue
            
            # Convert to absolute URL
            if href.startswith('/'):
                href = self.website.get_absolute_url(href)
            elif not href.startswith('http'):
                href = self.website.get_absolute_url('/' + href)
            
            # Extract title (optional)
            title = ''
            if self.website.position_title_selector:
                title_element = item.select_one(self.website.position_title_selector)
                if title_element:
                    title = title_element.text.strip()
            
            # Fallback: try common h4 if no title selector defined
            if not title:
                fallback = item.select_one('h4')
                if fallback:
                    title = fallback.text.strip()
            
            # Extract company (optional)
            company = ''
            if self.website.position_company_selector:
                company_element = item.select_one(self.website.position_company_selector)
                if company_element:
                    company = company_element.text.strip()
            
            results.append({
                'url': href,
                'title': title or 'Unknown Title',
                'company': company or '',
            })
        
        return results
    
    def iter_positions(self, max_pages: Optional[int] = None):
        """Yield each position dict one at a time."""
        if max_pages is None:
            max_pages = self.website.max_pages

        for page in range(1, max_pages + 1):
            results = self.extract_links_from_page(page)
            if not results:
                break
            for pos in results:
                yield pos


class PositionDetailExtractor:
    """
    Service to extract detailed information from a single position page.
    """
    
    def __init__(self, website: Website):
        """
        Initialize the detail extractor with a website configuration.
        
        Args:
            website: Website configuration object
        """
        self.website = website
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': website.user_agent,
        })
        self.timeout = website.request_timeout
        self.delay = website.request_delay
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a URL and return BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup: Parsed HTML or None if error
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            time.sleep(self.delay)
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def _extract_text_from_selector(self, soup: BeautifulSoup, selector: str) -> str:
        """
        Extract text from a CSS selector.
        
        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            
        Returns:
            str: Extracted text or empty string
        """
        if not selector or not soup:
            return ''
        
        # Handle multiple selectors separated by comma
        if ',' in selector:
            elements = soup.select(selector)
            return ' '.join([el.get_text(strip=True) for el in elements if el])
        
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ''
    
    def extract_details(self, url: str) -> Optional[Dict]:
        """
        Extract all details from a position page.
        
        Args:
            url: Position URL
            
        Returns:
            dict: Position details including title, company, and content
        """
        soup = self._fetch_page(url)
        
        if not soup:
            return None
        
        # Extract content from detail container
        detail_container = self._extract_text_from_selector(soup, self.website.detail_container_selector)
        
        return {
            'url': url,
            'cleaned_text': detail_container,
        }
    
    def extract_multiple(self, urls: List[str]) -> List[Dict]:
        """
        Extract details from multiple position URLs.
        
        Args:
            urls: List of position URLs
            
        Returns:
            List[Dict]: List of position details
        """
        results = []
        total = len(urls)
        
        for idx, url in enumerate(urls, 1):
            print(f"Extracting details {idx}/{total}: {url[:80]}...")
            details = self.extract_details(url)
            if details:
                results.append(details)
        
        return results


class PositionScraper:
    def __init__(self, website: Website):
        self.website = website
        self.link_extractor = PositionLinkExtractor(website)
        self.detail_extractor = PositionDetailExtractor(website)

    def scrape(self, max_pages: Optional[int] = None):
        """
        Generator that yields fully scraped position data one by one.
        """
        if max_pages is None:
            max_pages = self.website.max_pages

        print(f"\n🚀 Starting scrape for: {self.website.name}")
        print("=" * 60)

        for pos in self.link_extractor.iter_positions(max_pages):
            print(f"📌 Extracting: {pos['title'][:60]}...")
            
            details = self.detail_extractor.extract_details(pos['url'])
            if details:
                details['title'] = pos['title']
                details['company'] = pos['company']
                yield details
            else:
                print(f"  ⚠️ Failed to extract details for: {pos['title']}")

        print("\n🎉 Scraping complete!")


class ScrapeOrchestrator:
    """Orchestrates scraping and handles DB persistence with streaming."""

    def __init__(self, website: Website):
        self.website = website
        self.scraper = PositionScraper(website)

    def run(self, max_pages: Optional[int] = None) -> int:
        if max_pages is None:
            max_pages = self.website.max_pages

        saved = skipped = failed = 0
        print(f"\n🚀 Starting scrape for: {self.website.name} (max pages: {max_pages or 'unlimited'})")
        print("=" * 70)

        existing_urls = self._get_existing_urls()
        print(f"📊 Found {len(existing_urls)} existing positions.\n")

        for data in self.scraper.scrape(max_pages):
            if data['url'] in existing_urls:
                skipped += 1
                print(f"  ⏭️  [{skipped}] Skipping existing: {data['title'][:50]}...")
                continue
            try:
                self._save_position(data)
                saved += 1
                existing_urls.add(data['url'])
                print(f"  ✅ [{saved}] Saved: {data['title'][:50]}...")
            except Exception as e:
                failed += 1
                print(f"  ❌ Failed to save {data['title'][:50]}... - {e}")

        self.website.update_scrape_stats(saved)
        self._print_summary(saved, skipped, failed, max_pages)
        return saved

    def _get_existing_urls(self) -> Set[str]:
        return set(Position.objects.filter(website=self.website).values_list('url', flat=True))

    def _save_position(self, data: dict) -> Position:
        return Position.objects.create(
            website=self.website,
            status='SCRAPED',
            url=data.get('url', ''),
            title=data.get('title', 'Unknown Title'),
            company=data.get('company', ''),
            cleaned_text=data.get('cleaned_text', ''),
        )

    def _print_summary(self, saved: int, skipped: int, failed: int, max_pages: Optional[int]):
        print("\n" + "=" * 70)
        print("📊 SCRAPING SUMMARY")
        print("=" * 70)
        print(f"  ✅ Saved:     {saved}")
        print(f"  ⏭️  Skipped:   {skipped} (already in DB)")
        if failed:
            print(f"  ❌ Failed:    {failed}")
        print(f"  📄 Pages:     {max_pages or 'unlimited'}")
        print(f"  📁 Website:   {self.website.name}")
        print("=" * 70)
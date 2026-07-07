import scrapy
from bs4 import BeautifulSoup
from items import JobItem
from scrapy.exceptions import CloseSpider
import scrapy_playwright

class JobSpider(scrapy.Spider):
    name = "jobs"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playwright_tried = set()  # Track URLs tried with Playwright
    
    def start_requests(self):
        urls = ["https://books.toscrape.com/"]
        for url in urls:
            yield scrapy.Request(
                url, 
                callback=self.parse_deterministic,
                errback=self.errback
            )
    
    def parse_deterministic(self, response):
        """Phase 1: Fast BeautifulSoup parsing"""
        self.logger.info(f"Phase 1: Deterministic parsing {response.url}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        
        for card in soup.select('article.product_pod'):
            try:
                item_data = {
                    "url": response.urljoin(card.select_one('h3 a')['href']),
                    "title": card.select_one('h3 a')['title'],
                    "company": "Books Inc.",
                    "source": "bs4_deterministic"
                }
                valid_item = JobItem(**item_data)
                items.append(valid_item)
                yield valid_item.dict()
                
            except Exception as e:
                self.logger.debug(f"Card extraction failed: {e}")
                continue
        
        if not items:
            self.logger.warning(f"No items found deterministically for {response.url}")
            yield from self.fallback_to_playwright(response.url)
    
    def fallback_to_playwright(self, url):
        """Phase 2: Playwright rendering"""
        if url in self.playwright_tried:
            self.logger.error(f"Playwright already tried for {url}, moving to LLM rescue")
            # Trigger LLM rescue here
            return
        
        self.playwright_tried.add(url)
        self.logger.info(f"Phase 2: Trying Playwright for {url}")
        
        yield scrapy.Request(
            url,
            callback=self.parse_playwright,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_coroutines': [
                     scrapy_playwright.page.PageCoroutine('wait_for_selector', 'article.product_pod', timeout=10000)
                ]
            },
            errback=self.playwright_errback
        )
    
    async def parse_playwright(self, response):
        """Parse with Playwright-rendered content"""
        page = response.meta['playwright_page']
        
        try:
            # Wait for content
            # (Already waited via page_coroutines, but good double check)
            content = await page.content()
            
            soup = BeautifulSoup(content, 'html.parser')
            # Same extraction logic as parse_deterministic
            
            items_found = False
            for card in soup.select('article.product_pod'):
                try:
                    item_data = {
                        "url": response.urljoin(card.select_one('h3 a')['href']),
                        "title": card.select_one('h3 a')['title'],
                        "company": "Books Inc.",
                        "source": "playwright"
                    }
                    valid_item = JobItem(**item_data)
                    yield valid_item.dict()
                    items_found = True
                except Exception as e:
                    continue
            
            if not items_found:
                self.logger.error(f"Phase 2 failed: Playwright found no items")
                # Phase 3: LLM Rescue
                for item in self.trigger_llm_rescue(content):
                    yield item
                
        finally:
            await page.close()
    
    def trigger_llm_rescue(self, html_content):
        """Phase 3: LLM-based parsing"""
        self.logger.warning("Phase 3: LLM Rescue activated")
        # Generator that yields 0 items for now
        return []
    
    async def playwright_errback(self, failure):
        """Handle Playwright failures"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"Playwright request failed: {failure.value}")
    
    def errback(self, failure):
        """General error handling"""
        self.logger.error(f"Request failed: {failure.value}")
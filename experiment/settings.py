# Scrapy Settings for 'Experiment' Crawler

BOT_NAME = 'experiment_crawler'

SPIDER_MODULES = ['spiders']
NEWSPIDER_MODULE = 'spiders'

# Obey robots.txt
ROBOTSTXT_OBEY = True

# Concurrent Requests
CONCURRENT_REQUESTS = 16

# --- PLAYWRIGHT SETTINGS ---
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "timeout": 20 * 1000,  # 20 seconds
}

# --- MIDDLEWARES ---
# We will add our custom recovery middleware here later
# SPIDER_MIDDLEWARES = {
#    'experiment.middlewares.PlaywrightRecoveryMiddleware': 543,
# }

# --- PIPELINES ---
ITEM_PIPELINES = {
   'pipelines.validation.ValidationPipeline': 300,
}

# Logs
LOG_LEVEL = 'INFO'

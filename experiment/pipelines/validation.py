from items import JobItem
from scrapy.exceptions import DropItem

class ValidationPipeline:
    def process_item(self, item, spider):
        try:
            # Re-validate with Pydantic
            validated = JobItem(**item)
            spider.logger.debug(f"✓ Validated: {validated.title}")
            return validated.dict()  # Return as dict for consistency
        except ValidationError as e:
            spider.logger.error(f"Validation failed: {e}")
            raise DropItem(f"Invalid item: {e}")

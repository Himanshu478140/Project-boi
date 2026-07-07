from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional

class BaseItem(BaseModel):
    url: str
    source: str = "scanner"

class JobItem(BaseItem):
    title: str = Field(..., min_length=3)
    company: str = Field(..., min_length=1)
    location: Optional[str] = "Remote"
    salary: Optional[str] = None
    description_snippet: Optional[str] = None

    @validator('title')
    def title_must_be_real(cls, v):
        if "test" in v.lower() and len(v) < 5:
            raise ValueError('Title looks like a test artifact')
        return v

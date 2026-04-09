from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SearchCreate(BaseModel):
    tool_name: str


class SearchResponse(BaseModel):
    id: int
    tool_name: str
    status: str
    total_results: int
    created_at: str
    completed_at: Optional[str] = None


class ResultResponse(BaseModel):
    id: int
    search_id: int
    company_name: Optional[str]
    job_title: Optional[str]
    job_url: Optional[str]
    location: Optional[str]
    contract_type: Optional[str]
    tool_context: Optional[str]
    source: Optional[str]
    scraped_at: str

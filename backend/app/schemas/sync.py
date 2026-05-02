from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SyncRequest(BaseModel):
    from_date: str   # YYYY-MM-DD
    to_date: str     # YYYY-MM-DD


class SyncJobResponse(BaseModel):
    id: int
    tenant_id: str
    source: str
    status: str
    ref_date_from: str
    ref_date_to: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    records_fetched: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}

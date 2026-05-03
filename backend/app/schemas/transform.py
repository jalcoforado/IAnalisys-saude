from pydantic import BaseModel


class TransformResultItem(BaseModel):
    entity: str
    fetched: int
    inserted: int
    updated: int
    errors: int


class TransformResponse(BaseModel):
    results: list[TransformResultItem]
    total_inserted: int
    total_updated: int
    total_errors: int

from pydantic import BaseModel


class HiiScoreResponse(BaseModel):
    name: str
    score: int
    label: str
    summary: str
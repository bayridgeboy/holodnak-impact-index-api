from pydantic import BaseModel, Field
from typing import List, Optional, Literal

Confidence = Literal["low", "medium", "high"]

class PersonIn(BaseModel):
    name: str
    person_id: Optional[str] = None     # returned by backend, sent back by UI
    description: Optional[str] = None   # one-line disambiguation from user

class HiiRequest(BaseModel):
    people: List[PersonIn] = Field(min_length=1, max_length=3)
    rubric_version: str = "impact_v1"
    refresh: bool = False

class HiiCard(BaseModel):
    person_id: str
    name: str

    industry: str
    industry_impact: int  # 0..100
    totem: str            # one totem only
    funny: List[str]      # 1–2 lines
    defense: List[str]    # 1–3 bullets
    confidence: Confidence

    clarify_question: Optional[str] = None  # shows input under the card

class HiiOk(BaseModel):
    status: Literal["ok"] = "ok"
    rubric_version: str
    cards: List[HiiCard]
    image_url: Optional[str] = None

HiiResponse = HiiOk
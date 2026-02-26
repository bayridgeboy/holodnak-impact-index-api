from pydantic import BaseModel, Field
from typing import List, Optional, Literal

Confidence = Literal["low", "medium", "high"]

class PersonIn(BaseModel):
    name: str
    person_id: Optional[str] = None
    description: Optional[str] = None
    selected_url: Optional[str] = None

class HiiRequest(BaseModel):
    people: List[PersonIn] = Field(min_length=1, max_length=3)
    rubric_version: str = "impact_v1"
    refresh: bool = False

class Source(BaseModel):
    title: str
    url: str

class AlternateMatch(BaseModel):
    display: str
    url: str
    snippet: Optional[str] = None

class HiiCard(BaseModel):
    person_id: str
    name: str

    industry: str
    industry_impact: int
    totem: str
    funny: List[str]
    defense: List[str]
    confidence: Confidence

    sources: List[Source] = []
    alternates: List[AlternateMatch] = []
    clarify_question: Optional[str] = None

class HiiOk(BaseModel):
    status: Literal["ok"] = "ok"
    rubric_version: str
    cards: List[HiiCard]
    image_url: Optional[str] = None
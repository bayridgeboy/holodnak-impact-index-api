from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from urllib.parse import urlparse
import re

Confidence = Literal["low", "medium", "high"]

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _clean_text(value: str, *, max_len: int) -> str:
    value = _CONTROL_CHARS_RE.sub("", value).strip()
    value = re.sub(r"\s+", " ", value)
    if len(value) > max_len:
        raise ValueError(f"must be at most {max_len} characters")
    return value


def _validate_http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("must be a valid http(s) URL")
    return value

class PersonIn(BaseModel):
    name: str
    person_id: Optional[str] = None
    description: Optional[str] = None
    selected_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = _clean_text(v, max_len=80)
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _clean_text(v, max_len=64)
        if not v:
            return None
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _clean_text(v, max_len=240)
        return v or None

    @field_validator("selected_url")
    @classmethod
    def validate_selected_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _clean_text(v, max_len=2048)
        if not v:
            return None
        return _validate_http_url(v)

class HiiRequest(BaseModel):
    people: List[PersonIn] = Field(min_length=1, max_length=3)
    rubric_version: str = "impact_v1"
    refresh: bool = False

    @field_validator("rubric_version")
    @classmethod
    def validate_rubric_version(cls, v: str) -> str:
        v = _clean_text(v, max_len=32)
        if not v:
            raise ValueError("rubric_version cannot be empty")
        return v

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
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, conint, constr

Label = Literal["very_low", "low", "medium", "high", "very_high"]

class HiiPersonInput(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    description: Optional[constr(strip_whitespace=True, min_length=1)] = None

class HiiRequestV2(BaseModel):
    people: List[HiiPersonInput] = Field(..., min_length=1, max_length=3)
    # Optional conversation/session id if you want one-followup flow later
    session_id: Optional[str] = None

class HiiSubscores(BaseModel):
    scale: conint(ge=1, le=5)
    recognition: conint(ge=1, le=5)
    legacy: conint(ge=1, le=5)

class HiiPersonCard(BaseModel):
    name: str
    hii_score: conint(ge=0, le=100)
    label: Label
    tier: str
    subscores: HiiSubscores
    summary: str
    hot_take: str

class HiiNeedInputResponse(BaseModel):
    status: Literal["needs_input"]
    question: str
    # echo back names so UI can render placeholders later
    names: List[str]

class HiiOkResponse(BaseModel):
    status: Literal["ok"]
    people: List[HiiPersonCard]
    referee: Optional[str] = None
    disclaimer: str
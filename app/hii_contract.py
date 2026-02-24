from pydantic import BaseModel, Field
from typing import Literal


HiiLabel = Literal["very_low", "low", "medium", "high", "very_high"]


class HiiScoreRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Person name to score")


class HiiScoreResponse(BaseModel):
    name: str
    score: int = Field(..., ge=0, le=100)
    label: HiiLabel
    summary: str = Field(..., min_length=1, description="1-2 sentence summary")


# JSON Schema for OpenAI Structured Outputs (Responses API -> text.format)
HII_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "label": {
            "type": "string",
            "enum": ["very_low", "low", "medium", "high", "very_high"],
        },
        "summary": {"type": "string"},
    },
    "required": ["name", "score", "label", "summary"],
}
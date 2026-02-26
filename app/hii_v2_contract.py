from pydantic import BaseModel
from typing import Optional


class HiiPersonInput(BaseModel):
    name: str
    description: Optional[str] = None
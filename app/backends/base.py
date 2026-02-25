from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.hii_contract import HiiScoreResponse
from app.hii_v2_contract import HiiPersonInput


class HiiBackend(ABC):
    @abstractmethod
    def score_name(self, name: str) -> HiiScoreResponse:
        raise NotImplementedError

    @abstractmethod
    def score_v2(self, people: List[HiiPersonInput]) -> Dict[str, Any]:
        raise NotImplementedError
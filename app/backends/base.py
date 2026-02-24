from abc import ABC, abstractmethod

from app.hii_contract import HiiScoreResponse


class HiiBackend(ABC):
    @abstractmethod
    def score_name(self, name: str) -> HiiScoreResponse:
        raise NotImplementedError
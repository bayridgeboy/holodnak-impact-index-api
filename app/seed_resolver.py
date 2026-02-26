import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional

def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

@dataclass
class SeedPerson:
    name: str
    description: str

class SeedCatalog:
    def __init__(self, people: List[SeedPerson]):
        self.people = people
        self.by_norm = {_norm(p.name): p for p in people}

    @classmethod
    def load(cls) -> "SeedCatalog":
        base_dir = Path(__file__).resolve().parent           # /app/app
        default_seed = base_dir / "static" / "seed_people.json"
        data_path = os.getenv("HII_SEED_PATH", str(default_seed))

        try:
            with open(data_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            people = [SeedPerson(name=x["name"], description=x["description"]) for x in raw]
            return cls(people)
        except Exception as e:
            # Do NOT crash the whole app; return empty catalog so UI still works.
            print(f"[SeedCatalog] Failed to load seed file at {data_path}: {e}")
            return cls([])

    def exact(self, name: str) -> Optional[SeedPerson]:
        return self.by_norm.get(_norm(name))

    def top_candidates(self, name: str, k: int = 3) -> List[SeedPerson]:
        n = _norm(name)
        scored = [(p, _sim(n, _norm(p.name))) for p in self.people]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [p for p, score in scored[:k] if score >= 0.70]
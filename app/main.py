from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from app.ui_contract import HiiRequest, HiiOk, HiiCard, Source, AlternateMatch
from app.backends.openai_backend import OpenAIBackend

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

_backend = None

def get_backend() -> OpenAIBackend:
    global _backend
    if _backend is None:
        _backend = OpenAIBackend()
    return _backend

@app.get("/health")
def health():
    return {"status": "ok", "backend": os.getenv("HII_BACKEND", "openai")}

@app.post("/hii", response_model=HiiOk)
def hii(req: HiiRequest):
    # Always return cards immediately using OpenAI web search
    backend = get_backend()

    people_payload = [
        {"name": p.name, "description": p.description, "selected_url": p.selected_url}
        for p in req.people
    ]

    data = backend.score_ui_cards(people_payload)
    cards_raw = data.get("cards") or []

    cards = []
    for c in cards_raw:
        sources = [Source(**s) for s in (c.get("sources") or [])[:3] if isinstance(s, dict) and s.get("url")]
        alternates = [AlternateMatch(**a) for a in (c.get("alternates") or [])[:3] if isinstance(a, dict) and a.get("url")]

        clarify = c.get("clarify_question")
        if not clarify:
            clarify = f"If you meant a different {c.get('name','this person')}, pick another match below or paste one line and I’ll rescore."

        card = HiiCard(
            person_id=c.get("person_id", ""),
            name=c.get("name", ""),
            industry=c.get("industry", "Unknown"),
            industry_impact=int(c.get("industry_impact", 60)),
            totem=str(c.get("totem", "raccoon")),
            funny=list(c.get("funny") or [])[:2],
            defense=list(c.get("defense") or [])[:3],
            confidence=c.get("confidence", "low"),
            sources=sources,
            alternates=alternates,
            clarify_question=clarify,
        )
        cards.append(card)

    return HiiOk(rubric_version=req.rubric_version, cards=cards, image_url=None)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
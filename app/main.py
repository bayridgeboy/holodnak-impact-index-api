import os
from typing import Union

from fastapi import FastAPI, HTTPException

from app.hii_contract import HiiScoreRequest, HiiScoreResponse
from app.hii_v2_contract import HiiRequestV2, HiiNeedInputResponse, HiiOkResponse
from app.hii_logic import needs_one_followup, followup_question
from app.backends.base import HiiBackend
from app.backends.openai_backend import OpenAIBackend
from app.backends.openclaw_backend import OpenClawBackend

app = FastAPI(title="Holodnak Impact Index API", version="0.3.0")


def get_backend() -> HiiBackend:
    backend_name = os.getenv("HII_BACKEND", "openai").lower()

    if backend_name == "openai":
        return OpenAIBackend()
    if backend_name == "openclaw":
        return OpenClawBackend()

    raise RuntimeError(f"Unsupported HII_BACKEND: {backend_name}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": os.getenv("HII_BACKEND", "openai"),
        "openclaw_agent": os.getenv("OPENCLAW_AGENT", ""),
    }


@app.post("/score", response_model=HiiScoreResponse)
def score(req: HiiScoreRequest):
    try:
        backend = get_backend()
        return backend.score_name(req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hii", response_model=Union[HiiNeedInputResponse, HiiOkResponse])
def hii(req: HiiRequestV2):
    try:
        # One-follow-up rule: if we don't have enough info, ask exactly one simple question
        if needs_one_followup(req.people):
            return HiiNeedInputResponse(
                status="needs_input",
                question=followup_question(),
                names=[p.name for p in req.people],
            )

        backend = get_backend()
        result = backend.score_v2(req.people)

        # Safety net in case model forgets disclaimer
        if "disclaimer" not in result or not result.get("disclaimer"):
            result["disclaimer"] = "Playful heuristic based on limited input."

        return HiiOkResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
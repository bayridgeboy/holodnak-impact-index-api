import os

from fastapi import FastAPI, HTTPException

from app.hii_contract import HiiScoreRequest, HiiScoreResponse
from app.backends.base import HiiBackend
from app.backends.openai_backend import OpenAIBackend
from app.backends.openclaw_backend import OpenClawBackend

app = FastAPI(title="Holodnak Impact Index API", version="0.2.0")


def get_backend() -> HiiBackend:
    backend_name = os.getenv("HII_BACKEND", "openai").lower()

    if backend_name == "openai":
        return OpenAIBackend()
    if backend_name == "openclaw":
        return OpenClawBackend()

    raise RuntimeError(f"Unsupported HII_BACKEND: {backend_name}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score", response_model=HiiScoreResponse)
def score(req: HiiScoreRequest):
    try:
        backend = get_backend()
        return backend.score_name(req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
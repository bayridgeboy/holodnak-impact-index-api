from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import re
import time
from urllib.parse import urlparse

from app.ui_contract import HiiRequest, HiiOk, HiiCard, Source, AlternateMatch
from app.backends.openai_backend import OpenAIBackend

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

_backend = None

MAX_REQUEST_BYTES = int(os.getenv("HII_MAX_REQUEST_BYTES", "32768"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("HII_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_REQUESTS = int(os.getenv("HII_RATE_LIMIT_REQUESTS", "30"))

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _clean_text(value: object, *, max_len: int, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    cleaned = _CONTROL_CHARS_RE.sub("", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return default
    return cleaned[:max_len]


def _clean_url(value: object) -> str | None:
    url = _clean_text(value, max_len=2048)
    if not url:
        return None
    if not _is_http_url(url):
        return None
    return url


def _clean_string_list(value: object, *, max_items: int, max_len: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        cleaned = _clean_text(item, max_len=max_len)
        if cleaned:
            out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


def _clean_confidence(value: object) -> str:
    if value in ("low", "medium", "high"):
        return value
    return "low"


@app.middleware("http")
async def abuse_guardrails(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/hii":
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": "request too large"})

        ip = _client_ip(request)
        now = time.time()
        bucket = _rate_buckets[ip]
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS

        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT_REQUESTS:
            retry_after = max(1, int(bucket[0] + RATE_LIMIT_WINDOW_SECONDS - now))
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)

    return await call_next(request)

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
        {
            "name": _clean_text(p.name, max_len=80),
            "description": _clean_text(p.description, max_len=240) if p.description else None,
            "selected_url": _clean_url(p.selected_url),
        }
        for p in req.people
    ]

    try:
        data = backend.score_ui_cards(people_payload)
    except Exception as e:
        message = str(e) or "backend error"
        if "invalid_api_key" in message or "Incorrect API key" in message or "AuthenticationError" in message:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "error",
                    "error": "OpenAI authentication failed. Update OPENAI_API_KEY and recreate the API container.",
                },
            )
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "error": "Upstream scoring backend failed. Check API logs.",
            },
        )
    cards_raw = data.get("cards") or []

    cards = []
    for c in cards_raw:
        raw_sources = (c.get("sources") or [])[:3]
        sources = []
        for s in raw_sources:
            if not isinstance(s, dict):
                continue
            url = _clean_url(s.get("url"))
            if not url:
                continue
            title = _clean_text(s.get("title"), max_len=200, default=url)
            sources.append(Source(title=title, url=url))

        raw_alternates = (c.get("alternates") or [])[:3]
        alternates = []
        for a in raw_alternates:
            if not isinstance(a, dict):
                continue
            alt_url = _clean_url(a.get("url"))
            if not alt_url:
                continue
            display = _clean_text(a.get("display"), max_len=200, default=alt_url)
            snippet = _clean_text(a.get("snippet"), max_len=300) or None
            alternates.append(AlternateMatch(display=display, url=alt_url, snippet=snippet))

        clean_name = _clean_text(c.get("name"), max_len=80)
        clarify = _clean_text(c.get("clarify_question"), max_len=220) or None
        if not clarify:
            clarify = f"If you meant a different {clean_name or 'this person'}, pick another match below or paste one line and I’ll rescore."

        industry_impact = c.get("industry_impact", 60)
        try:
            industry_impact = int(industry_impact)
        except Exception:
            industry_impact = 60
        industry_impact = max(0, min(100, industry_impact))

        card = HiiCard(
            person_id=_clean_text(c.get("person_id"), max_len=64),
            name=clean_name,
            industry=_clean_text(c.get("industry"), max_len=80, default="Unknown"),
            industry_impact=industry_impact,
            totem=_clean_text(c.get("totem"), max_len=24, default="raccoon").lower(),
            funny=_clean_string_list(c.get("funny"), max_items=2, max_len=180),
            defense=_clean_string_list(c.get("defense"), max_items=3, max_len=180),
            confidence=_clean_confidence(c.get("confidence")),
            sources=sources,
            alternates=alternates,
            clarify_question=clarify,
        )
        cards.append(card)

    return HiiOk(rubric_version=req.rubric_version, cards=cards, image_url=None)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
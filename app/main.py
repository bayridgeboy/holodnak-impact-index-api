from collections import defaultdict, deque
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import re
import time
import logging
import hashlib
import json
from typing import Dict, Tuple, Any
from urllib.parse import urlparse

from app.ui_contract import HiiRequest, HiiOk, HiiCard, Source, AlternateMatch
from app.backends.openai_backend import OpenAIBackend

# Configure logging
LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "hii_requests.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also log to stdout for docker-compose logs
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

_backend = None

MAX_REQUEST_BYTES = int(os.getenv("HII_MAX_REQUEST_BYTES", "32768"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("HII_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_REQUESTS = int(os.getenv("HII_RATE_LIMIT_REQUESTS", "30"))
CACHE_TTL_SECONDS = int(os.getenv("HII_CACHE_TTL_SECONDS", "3600"))  # 1 hour default

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)

# Response cache: {cache_key: (response_data, expiration_timestamp)}
_response_cache: Dict[str, Tuple[Any, float]] = {}
_cache_hits = 0
_cache_misses = 0

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


def _make_cache_key(people_payload: list) -> str:
    """Create a stable cache key from people payload."""
    # Sort by name to handle different orderings
    sorted_payload = sorted(people_payload, key=lambda p: p.get("name", "").lower())
    cache_str = json.dumps(sorted_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cache_str.encode("utf-8")).hexdigest()[:16]


def _get_cached_response(cache_key: str) -> Any | None:
    """Get cached response if it exists and hasn't expired."""
    global _cache_hits, _cache_misses
    
    if cache_key in _response_cache:
        cached_data, expiration = _response_cache[cache_key]
        if time.time() < expiration:
            _cache_hits += 1
            return cached_data
        else:
            # Expired, remove it
            del _response_cache[cache_key]
    
    _cache_misses += 1
    return None


def _set_cached_response(cache_key: str, data: Any) -> None:
    """Cache a response with TTL."""
    expiration = time.time() + CACHE_TTL_SECONDS
    _response_cache[cache_key] = (data, expiration)
    
    # Simple cleanup: remove expired entries if cache grows large
    if len(_response_cache) > 1000:
        now = time.time()
        expired_keys = [k for k, (_, exp) in _response_cache.items() if exp < now]
        for k in expired_keys:
            del _response_cache[k]


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

@app.get("/cache-stats")
def cache_stats():
    """Return cache statistics."""
    now = time.time()
    active_entries = sum(1 for _, exp in _response_cache.values() if exp > now)
    total_requests = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total_requests * 100) if total_requests > 0 else 0
    
    return {
        "cache_hits": _cache_hits,
        "cache_misses": _cache_misses,
        "total_requests": total_requests,
        "hit_rate_percent": round(hit_rate, 2),
        "active_entries": active_entries,
        "cache_size": len(_response_cache),
        "ttl_seconds": CACHE_TTL_SECONDS,
    }

@app.post("/hii", response_model=HiiOk)
def hii(req: HiiRequest):
    # Log submitted names
    names = [p.name for p in req.people]
    logger.info(f"HII request: {', '.join(names)}")
    
    backend = get_backend()

    people_payload = [
        {
            "name": _clean_text(p.name, max_len=80),
            "description": _clean_text(p.description, max_len=240) if p.description else None,
            "selected_url": _clean_url(p.selected_url),
        }
        for p in req.people
    ]

    # Check cache first (unless refresh is requested)
    cache_key = _make_cache_key(people_payload)
    if not req.refresh:
        cached = _get_cached_response(cache_key)
        if cached is not None:
            logger.info(f"Cache HIT for: {', '.join(names)}")
            data = cached
        else:
            logger.info(f"Cache MISS for: {', '.join(names)}")
            data = None
    else:
        logger.info(f"Cache BYPASS (refresh) for: {', '.join(names)}")
        data = None

    # If not cached, call backend
    if data is None:
        try:
            data = backend.score_ui_cards(people_payload)
            # Cache the response
            _set_cached_response(cache_key, data)
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
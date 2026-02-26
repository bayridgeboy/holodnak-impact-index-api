import json
import os
import hashlib
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.backends.base import HiiBackend
from app.hii_contract import HiiScoreResponse
from app.hii_v2_contract import HiiPersonInput
from app.prompts import build_hii_scorecards_prompt

from app.prompts_ui import build_hii_ui_prompt


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _pid_from_best(best_url: Optional[str], name: str) -> str:
    base = (best_url or name).strip().lower()
    h = hashlib.sha256(base.encode("utf-8")).hexdigest()[:14]
    return f"p_{h}"


class OpenAIBackend(HiiBackend):
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        # Enable hosted web search tool in Responses API
        self.enable_web_search = _env_bool("OPENAI_WEB_SEARCH", default=True)
        self.web_search_required = _env_bool("OPENAI_WEB_SEARCH_REQUIRED", default=True)

    # ---- v1 (keep old endpoint working) ----
    def score_name(self, name: str) -> HiiScoreResponse:
        result = self.score_v2([HiiPersonInput(name=name)])
        if not result.get("people"):
            raise RuntimeError("OpenAI returned no people in v2 response")
        card = result["people"][0]
        return HiiScoreResponse(
            name=card["name"],
            score=card["hii_score"],
            label=card["label"],
            summary=card["summary"],
        )

    # ---- v2 (single + compare cards) ----
    def score_v2(self, people: List[HiiPersonInput]) -> Dict[str, Any]:
        prompt = build_hii_scorecards_prompt(people)
        raw_text = self._call_openai_text(prompt, web_search=False)
        return self._parse_json(raw_text)

    # ---- UI cards (new) ----
    def score_ui_cards(self, people: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Input: [{"name": "...", "description": "...|None", "selected_url": "...|None"}, ...]
        Output: {"cards":[...]} (see prompts_ui.py schema)
        """
        prompt = build_hii_ui_prompt(people)
        raw_text = self._call_openai_text(prompt, web_search=self.enable_web_search)
        data = self._parse_json(raw_text)

        # Ensure person_id exists and best_url is present (or None)
        cards = data.get("cards") or []
        for c in cards:
            best_url = c.get("best_url")
            c["person_id"] = _pid_from_best(best_url, c.get("name", ""))
            # normalize funny length
            if isinstance(c.get("funny"), list):
                c["funny"] = c["funny"][:2]
        data["cards"] = cards
        return data

    def _call_openai_text(self, prompt: str, *, web_search: bool = False) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "temperature": 0.2,
        }

        if web_search:
            kwargs["tools"] = [{"type": "web_search"}]
            if self.web_search_required:
                kwargs["tool_choice"] = "required"
            # include sources in tool output (model still returns JSON-only; sources are for debugging if needed)
            kwargs["include"] = ["web_search_call.action.sources"]

        resp = self.client.responses.create(**kwargs)

        text = getattr(resp, "output_text", None)
        if text:
            return text.strip()

        # fallback extraction
        try:
            parts: List[str] = []
            for item in resp.output:
                if getattr(item, "type", None) != "message":
                    continue
                for c in getattr(item, "content", []):
                    if getattr(c, "type", None) in ("output_text", "text"):
                        t = getattr(c, "text", None)
                        if t:
                            parts.append(t)
            joined = "\n".join(parts).strip()
            if joined:
                return joined
        except Exception:
            pass

        raise RuntimeError(f"Could not extract text from OpenAI response: {resp}")

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            cleaned = self._extract_first_json_object(raw_text)
            if cleaned is None:
                raise RuntimeError(f"OpenAI returned invalid JSON: {e}\nRAW:\n{raw_text}")
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e2:
                raise RuntimeError(f"OpenAI returned invalid JSON even after cleanup: {e2}\nRAW:\n{raw_text}")

    @staticmethod
    def _extract_first_json_object(text: str) -> Optional[str]:
        if not text:
            return None
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_str = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None
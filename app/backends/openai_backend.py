import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from app.backends.base import HiiBackend
from app.hii_contract import HiiScoreResponse
from app.hii_v2_contract import HiiPersonInput
from app.prompts import build_hii_scorecards_prompt


class OpenAIBackend(HiiBackend):
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        
    # ---- v1 (keep old endpoint working) ----
    def score_name(self, name: str) -> HiiScoreResponse:
        # Reuse v2 path to avoid duplicate logic
        result = self.score_v2([HiiPersonInput(name=name)])

        if not result.get("people"):
            raise RuntimeError("OpenAI returned no people in v2 response")

        card = result["people"][0]

        # Map v2 card -> old v1 response
        return HiiScoreResponse(
            name=card["name"],
            score=card["hii_score"],
            label=card["label"],
            summary=card["summary"],
        )

    # ---- v2 (single + compare cards) ----
    def score_v2(self, people: List[HiiPersonInput]) -> Dict[str, Any]:
        prompt = build_hii_scorecards_prompt(people)

        raw_text = self._call_openai_text(prompt)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            cleaned = self._extract_first_json_object(raw_text)
            if cleaned is None:
                raise RuntimeError(f"OpenAI returned invalid JSON: {e}\nRAW:\n{raw_text}")
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e2:
                raise RuntimeError(f"OpenAI returned invalid JSON even after cleanup: {e2}\nRAW:\n{raw_text}")

        return data

    def _call_openai_text(self, prompt: str) -> str:
        """
        Calls OpenAI Responses API and returns plain text output.
        Keeps output short/predictable for JSON responses.
        """
        resp = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,  # low randomness helps JSON consistency
        )

        # Robust text extraction for Responses API
        text = getattr(resp, "output_text", None)
        if text:
            return text.strip()

        # Fallback extraction if SDK shape differs
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

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        """
        Best-effort extractor for the first top-level JSON object.
        Useful if the model wraps JSON in code fences or extra text.
        """
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
                    return text[start:i + 1]

        return None
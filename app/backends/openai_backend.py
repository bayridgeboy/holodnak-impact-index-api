import json
import os

import requests

from app.backends.base import HiiBackend
from app.hii_contract import HiiScoreResponse, HII_OUTPUT_SCHEMA


def _extract_text_from_responses_api(resp_json: dict) -> str:
    parts: list[str] = []

    for item in resp_json.get("output", []):
        if item.get("type") != "message":
            continue

        for content_item in item.get("content", []):
            ctype = content_item.get("type")
            if ctype in ("output_text", "text"):
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)

    if not parts:
        raise ValueError(f"No text found in OpenAI response: {json.dumps(resp_json)[:2000]}")

    return "\n".join(parts).strip()


class OpenAIBackend(HiiBackend):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def score_name(self, name: str) -> HiiScoreResponse:
        system_prompt = (
            "You score people for a Human Impact Index (HII). "
            "Be balanced and concise. Use broad historical/cultural/scientific/social impact."
        )

        user_prompt = f"Score this person for HII: {name}"

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "hii_score",
                    "strict": True,
                    "schema": HII_OUTPUT_SCHEMA,
                }
            },
        }

        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(f"OpenAI API error: {r.status_code} {r.text}") from e

        text = _extract_text_from_responses_api(r.json())

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Model returned non-JSON text: {text}") from e

        return HiiScoreResponse.model_validate(parsed)
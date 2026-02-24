import json
import os

import requests
from fastapi import FastAPI, HTTPException

from app.hii_contract import HiiScoreRequest, HiiScoreResponse, HII_OUTPUT_SCHEMA

app = FastAPI(title="Holodnak Impact Index API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


def _extract_text_from_responses_api(resp_json: dict) -> str:
    """
    Raw Responses API returns an `output` array.
    We collect text from message content items (output_text/text).
    """
    parts = []

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


def score_name_with_openai(name: str) -> HiiScoreResponse:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    system_prompt = (
        "You score people for a Human Impact Index (HII). "
        "Be balanced and concise. Use broad historical/cultural/scientific/social impact."
    )

    user_prompt = f"Score this person for HII: {name}"

    payload = {
        "model": "gpt-4o",
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"OpenAI API error: {r.status_code} {r.text}") from e

    data = r.json()
    text = _extract_text_from_responses_api(data)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model returned non-JSON text: {text}") from e

    # Validate against our API contract before returning
    return HiiScoreResponse.model_validate(parsed)


@app.post("/score", response_model=HiiScoreResponse)
def score(req: HiiScoreRequest):
    try:
        return score_name_with_openai(req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
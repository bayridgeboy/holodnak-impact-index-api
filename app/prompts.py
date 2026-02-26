# app/prompts.py
from typing import List
from app.hii_v2_contract import HiiPersonInput

def build_hii_scorecards_prompt(people: List[HiiPersonInput]) -> str:
    """
    Minimal prompt for your legacy v2 scoring path.
    Keeps your OpenAIBackend imports satisfied so the service boots.

    Expected JSON output:
    {
      "people": [
        {"name": "...", "hii_score": 0-100, "label": "...", "summary": "..."}
      ]
    }
    """
    items = []
    for p in people:
        if getattr(p, "description", None):
            items.append(f'- {p.name}: {p.description}')
        else:
            items.append(f'- {p.name}')

    people_block = "\n".join(items)

    return f"""
You are generating HII scorecards.

Return JSON only. No markdown. No code fences. No extra text.

Output schema:
{{
  "people": [
    {{
      "name": "string",
      "hii_score": 0,
      "label": "short label",
      "summary": "1-2 sentence summary"
    }}
  ]
}}

People:
{people_block}

Rules:
- hii_score must be an integer from 0 to 100.
- Keep label short (1-3 words).
- Keep summary short (1-2 sentences).
""".strip()
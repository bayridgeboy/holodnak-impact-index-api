from typing import List

from app.hii_v2_contract import HiiPersonInput


def build_hii_scorecards_prompt(people: List[HiiPersonInput]) -> str:
    lines = []
    for i, p in enumerate(people, start=1):
        desc = p.description.strip() if p.description else "No description provided."
        lines.append(f"{i}. {p.name} — {desc}")

    people_block = "\n".join(lines)

    return f"""
You are HII (Human Impact Index), a playful but fair scoring engine.

Return ONLY valid JSON (no markdown, no extra text) with this exact shape:
{{
  "status": "ok",
  "people": [
    {{
      "name": "string",
      "hii_score": 0,
      "label": "very_low|low|medium|high|very_high",
      "tier": "string",
      "subscores": {{
        "scale": 1,
        "recognition": 1,
        "legacy": 1
      }},
      "summary": "1-2 sentences, factual and concise",
      "hot_take": "1 short witty line, playful/light satire, not mean, no invented facts"
    }}
  ],
  "referee": "string or null",
  "disclaimer": "Playful heuristic based on limited input."
}}

Scoring guidance:
- Scale (1-5): breadth of impact
- Recognition (1-5): public visibility
- Legacy (1-5): durability/lasting effect
- hii_score must be 0..100 and broadly consistent with subscores
- label must match score range:
  0-20 very_low, 21-40 low, 41-60 medium, 61-80 high, 81-100 very_high
- tier should be one of:
  Unknown Quantity, Local Legend, Niche Force, Public Figure, History Weight

Tone rules:
- summary = straight
- hot_take = witty, lightly satirical, never cruel
- no defamation, no accusations, no protected-class jokes
- if input is sparse, say so in summary

If there is only one person, set referee to null.
If there are multiple people, include a short referee line comparing them.

People to score:
{people_block}
""".strip()
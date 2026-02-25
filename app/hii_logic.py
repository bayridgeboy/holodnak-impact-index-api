from typing import List
from app.hii_v2_contract import HiiPersonInput

# Very small heuristic for now (we can improve later)
FAMOUS_HINTS = {
    "winston churchill", "mark zuckerberg", "leon trotsky", "albert einstein",
    "elon musk", "donald trump", "vladimir putin"
}

def needs_one_followup(people: List[HiiPersonInput]) -> bool:
    # If every person has a description, we have enough to score.
    if all(p.description for p in people):
        return False

    # If all names are obviously famous, no follow-up needed.
    all_famous = all(p.name.strip().lower() in FAMOUS_HINTS for p in people)
    if all_famous:
        return False

    return True

def followup_question() -> str:
    return "Give me one short line for each person (who they are / what they’re known for)."

def tier_from_score(score: int) -> str:
    if score <= 20:
        return "Unknown Quantity"
    if score <= 40:
        return "Local Legend"
    if score <= 60:
        return "Niche Force"
    if score <= 80:
        return "Public Figure"
    return "History Weight"
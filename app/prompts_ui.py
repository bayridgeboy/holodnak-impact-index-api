from typing import List, Optional, Dict, Any

def build_hii_ui_prompt(people: List[Dict[str, Any]]) -> str:
    """
    people items look like:
      {"name": "...", "selected_url": "...|None", "description": "...|None"}
    """

    lines = []
    lines.append("You are generating HII-style score cards.")
    lines.append("")
    lines.append("You MUST use web search results (tool) when available.")
    lines.append("Return JSON only. No markdown. No code fences. No extra text.")
    lines.append("")
    lines.append("For each person:")
    lines.append("1) Research the person matching this exact name.")
    lines.append("   - If selected_url is provided, treat that as the correct match anchor.")
    lines.append("   - If description is provided, use it as additional context (company/role/domain) to identify the correct match.")
    lines.append("2) Also return up to 3 alternate plausible matches (display, url, snippet).")
    lines.append("3) Produce a short snappy card with:")
    lines.append("   - industry (string)")
    lines.append("   - industry_impact (int 0..100)")
    lines.append("   - totem (ONE animal word, lowercase)")
    lines.append("   - funny: 1-2 slightly sarcastic lines (professional vibe only; no appearance/identity/personal life)")
    lines.append("   - defense: 2-3 short bullets that defend the score using evidence")
    lines.append('   - confidence: "low"|"medium"|"high"')
    lines.append("   - sources: 2-3 urls used (title + url)")
    lines.append("")
    lines.append("Safety/accuracy rules:")
    lines.append("- The 'name' field in the output must exactly match the input name provided (do not change or normalize it based on search results).")
    lines.append("- If the identity is ambiguous or evidence is weak: confidence=low, keep industry generic, avoid naming a specific employer.")
    lines.append("- Do NOT fabricate facts not supported by snippets/sources.")
    lines.append("- URLs must be plain strings (no markdown links).")
    lines.append("")
    lines.append("Output JSON schema:")
    lines.append("""
{
  "cards": [
    {
      "name": "...",
      "best_url": "... or null",
      "industry": "...",
      "industry_impact": 0,
      "totem": "osprey",
      "funny": ["...", "..."],
      "defense": ["...", "..."],
      "confidence": "low",
      "sources": [{"title":"...","url":"..."}],
      "alternates": [{"display":"...","url":"...","snippet":"..."}],
      "clarify_question": "If you meant a different X, pick another match or paste one line and I’ll rescore."
    }
  ]
}
""".strip())

    lines.append("")
    lines.append("People to score (JSON):")
    lines.append(str(people))

    return "\n".join(lines)
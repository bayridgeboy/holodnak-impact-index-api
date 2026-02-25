# app/backends/openclaw_backend.py

import json
import os
import subprocess
from typing import Any, Dict, List

from app.backends.base import HiiBackend
from app.hii_contract import HiiScoreResponse
from app.hii_v2_contract import HiiPersonInput
from app.prompts import build_hii_scorecards_prompt


class OpenClawBackend(HiiBackend):
    def __init__(self) -> None:
        # Optional knobs; keep defaults sane
        self.profile = os.getenv("OPENCLAW_PROFILE", "hii")
        self.agent = os.getenv("OPENCLAW_AGENT", "main")
        self.local = os.getenv("OPENCLAW_LOCAL", "true").lower() == "true"
        self.thinking = os.getenv("OPENCLAW_THINKING", "low")
        self.timeout_seconds = int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "240"))

    # ---- v1 (keep old endpoint working) ----
    def score_name(self, name: str) -> HiiScoreResponse:
        # Reuse v2 path so all scoring logic lives in one place
        result = self.score_v2([HiiPersonInput(name=name)])

        if not result.get("people"):
            raise RuntimeError("OpenClaw returned no people in v2 response")

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
        raw_text = self._call_openclaw_text(prompt)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            # OpenClaw/model may sometimes return extra text around JSON
            cleaned = self._extract_first_json_object(raw_text)
            if cleaned is None:
                raise RuntimeError(f"OpenClaw returned invalid JSON: {e}\nRAW:\n{raw_text}")
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e2:
                raise RuntimeError(f"OpenClaw returned invalid JSON even after cleanup: {e2}\nRAW:\n{raw_text}")

        return data

    def _call_openclaw_text(self, prompt: str) -> str:
        # --- Prompt slimming: keep only the dynamic part (people list) ---
        marker = "People to score:"
        if marker in prompt:
            prompt = marker + "\n" + prompt.split(marker, 1)[1].strip()

        # Hard cap as extra safety (prevents accidental massive prompts)
        MAX_CHARS = 2000
        if len(prompt) > MAX_CHARS:
            prompt = prompt[:MAX_CHARS] + "\n..."

        cmd = [
            "openclaw",
            "--profile",
            self.profile,
            "--no-color",
            "agent",
            "--message",
            prompt,
            "--agent",
            self.agent,
        ]

        if self.local:
            cmd.append("--local")

        if self.thinking:
            cmd.extend(["--thinking", self.thinking])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"OpenClaw failed (exit {proc.returncode})\n"
                f"CMD: {' '.join(cmd)}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )

        return (proc.stdout or "").strip()

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        """
        Best-effort extractor for the first top-level JSON object.
        Useful if the model wraps JSON in chatter or code fences.
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
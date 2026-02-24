import json
import os
import re
import shlex
import subprocess

from app.backends.base import HiiBackend
from app.hii_contract import HiiScoreResponse


def _extract_json_object(text: str) -> dict:
    text = text.strip()

    # Try direct parse first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object from noisy CLI output
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise RuntimeError(f"OpenClaw output did not contain JSON:\n{text[:2000]}")
    return json.loads(m.group(0))


class OpenClawBackend(HiiBackend):
    """
    Calls OpenClaw CLI as a subprocess.

    Important:
    - Do NOT pass --model here (openclaw agent doesn't support it).
    - Model must be configured in OpenClaw itself (models set ...).
    """

    def __init__(self) -> None:
        self.profile = os.getenv("OPENCLAW_PROFILE", "hii")

        # Force a sane default so we always pass --agent main unless overridden
        self.agent = os.getenv("OPENCLAW_AGENT", "main")

        self.session_id = os.getenv("OPENCLAW_SESSION_ID")  # optional
        self.use_local = os.getenv("OPENCLAW_LOCAL", "true").lower() == "true"
        self.thinking = os.getenv("OPENCLAW_THINKING", "low")

        # Optional exact command override if CLI syntax differs
        # Example: OPENCLAW_CMD="openclaw --profile hii --no-color agent"
        self.cmd_override = os.getenv("OPENCLAW_CMD")

    def score_name(self, name: str) -> HiiScoreResponse:
        system_prompt = (
            "You score people for a Human Impact Index (HII). "
            "Return ONLY valid JSON with exactly these keys: "
            "name, score, label, summary. "
            "score must be integer 0..100. "
            "label must be one of: very_low, low, medium, high, very_high. "
            "summary must be 1-2 sentences. No markdown, no extra text."
        )
        user_prompt = f"Score this person for HII: {name}"
        message = f"{system_prompt}\n\n{user_prompt}"

        if self.cmd_override:
            cmd = shlex.split(self.cmd_override)
        else:
            # Global flags first, then subcommand
            cmd = ["openclaw", "--profile", self.profile, "--no-color", "agent"]

        cmd += ["--message", message]

        # DO NOT pass --model here (unsupported by `openclaw agent`)
        if self.agent:
            cmd += ["--agent", self.agent]
        if self.session_id:
            cmd += ["--session-id", self.session_id]
        if self.use_local:
            cmd += ["--local"]
        if self.thinking:
            cmd += ["--thinking", self.thinking]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"OpenClaw failed (exit {proc.returncode})\n"
                f"CMD: {' '.join(shlex.quote(x) for x in cmd)}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )

        parsed = _extract_json_object(proc.stdout)
        return HiiScoreResponse.model_validate(parsed)
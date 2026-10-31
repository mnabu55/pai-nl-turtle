import json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from nl_turtle.plan import Pose2D

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
REQUEST_TIMEOUT_SEC = 60
MAX_ATTEMPTS = 3
RETRY_STATUS = {429, 500, 503}

PROMPT_TEMPLATE = """You control a turtle robot on a 2D field from (0, 0) to (11, 11) meters.
The robot is now at x={x:.2f}, y={y:.2f}, facing {heading:.0f} degrees (0 = +x direction, counter-clockwise positive).
Convert the user's instruction into motion steps.
Return ONLY a JSON object, no prose, no code fences, in this exact shape:
{{"steps": [{{"type": "forward", "value": <meters, negative = backward>}}, {{"type": "turn", "value": <degrees, positive = left/counter-clockwise>}}]}}
Rules:
- Never output a step whose value is 0.
- Do not add steps the user did not ask for (e.g. do not restore the original heading unless needed to complete a shape).
- Use the distances the user states as-is, even if they look too large; a separate checker decides whether they are safe.
- For a closed shape (polygon, star, etc.), turn in the same direction every time and make the path end where it started.
  For example, a five-pointed star is 5 x (forward, turn 144 degrees), all turns with the same sign.
User instruction: {instruction}"""


class PlannerError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    """Minimal .env loader so the ROS container needs no extra packages; existing env vars win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_prompt(instruction: str, pose: Pose2D) -> str:
    return PROMPT_TEMPLATE.format(x=pose.x, y=pose.y, heading=math.degrees(pose.theta), instruction=instruction)


def extract_json(text: str) -> Any:
    """Models sometimes wrap JSON in ``` fences despite instructions; take the outermost object."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise PlannerError(f"no JSON object in model output: {text[:200]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise PlannerError(f"invalid JSON in model output: {exc}") from exc


def _output_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for step in response.get("steps", []):
        if step.get("type") == "model_output":
            parts.extend(c.get("text", "") for c in step.get("content", []))
    if not parts:
        raise PlannerError(f"no model_output in response (status={response.get('status')!r})")
    return "".join(parts)


def call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise PlannerError("GEMINI_API_KEY is not set (put it in .env at the repository root)")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        API_URL, data=body, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as resp:
                return _output_text(json.load(resp))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            last_error = PlannerError(f"HTTP {exc.code} from {model}: {detail}")
            if exc.code not in RETRY_STATUS:
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = PlannerError(f"network error calling {model}: {exc}")
        logger.warning("Gemini attempt %d/%d failed: %s", attempt, MAX_ATTEMPTS, last_error)
        if attempt < MAX_ATTEMPTS:
            time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def plan_from_instruction(instruction: str, pose: Pose2D) -> Any:
    return extract_json(call_gemini(build_prompt(instruction, pose)))

import math
from dataclasses import dataclass, field
from typing import Any

from nl_turtle.plan import Pose2D, Step

FIELD_MIN = 0.5
FIELD_MAX = 10.5
MAX_STEPS = 20
MAX_FORWARD_METERS = 5.0
MAX_TURN_DEGREES = 360.0
TURN_CHUNK_DEGREES = 90.0


@dataclass
class ValidationResult:
    steps: list[Step] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_steps(raw: Any, errors: list[str]) -> list[Step]:
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
        errors.append('output must be an object with a "steps" list')
        return []
    items = raw["steps"]
    if not items:
        errors.append("steps is empty")
    if len(items) > MAX_STEPS:
        errors.append(f"too many steps: {len(items)} > {MAX_STEPS}")

    steps: list[Step] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"step {i}: not an object")
            continue
        kind = item.get("type")
        value = item.get("value")
        if kind not in ("forward", "turn"):
            errors.append(f"step {i}: unknown type {kind!r}")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"step {i}: value must be a finite number, got {value!r}")
            continue
        if value == 0:
            # A zero step is a harmless no-op that LLMs like to pad plans with; drop it instead of failing.
            continue
        if kind == "forward" and abs(value) > MAX_FORWARD_METERS:
            errors.append(f"step {i}: forward must be within ±{MAX_FORWARD_METERS} m, got {value}")
            continue
        if kind == "turn" and abs(value) > MAX_TURN_DEGREES:
            errors.append(f"step {i}: turn must be within ±{MAX_TURN_DEGREES} deg, got {value}")
            continue
        steps.append(Step(kind, float(value)))
    if items and not steps and not errors:
        errors.append("no effective steps (all steps were zero)")
    return steps


def split_turns(steps: list[Step]) -> list[Step]:
    """Split turns so each chunk is <= 90 deg; the executor's angle wrap cannot express 360 deg directly."""
    result: list[Step] = []
    for step in steps:
        if step.type != "turn":
            result.append(step)
            continue
        remaining = step.value
        while abs(remaining) > TURN_CHUNK_DEGREES:
            chunk = math.copysign(TURN_CHUNK_DEGREES, remaining)
            result.append(Step("turn", chunk))
            remaining -= chunk
        if remaining:
            result.append(Step("turn", remaining))
    return result


def max_travel(x: float, y: float, dx: float, dy: float) -> float:
    """Distance from (x, y) along unit direction (dx, dy) before leaving the allowed field."""
    limit = math.inf
    for pos, d in ((x, dx), (y, dy)):
        if d > 1e-9:
            limit = min(limit, (FIELD_MAX - pos) / d)
        elif d < -1e-9:
            limit = min(limit, (FIELD_MIN - pos) / d)
    return max(0.0, limit)


def _check_bounds(steps: list[Step], start: Pose2D, errors: list[str]) -> None:
    x, y, theta = start.x, start.y, start.theta
    for i, step in enumerate(steps, start=1):
        if step.type == "turn":
            theta += math.radians(step.value)
            continue
        dx = math.copysign(1.0, step.value) * math.cos(theta)
        dy = math.copysign(1.0, step.value) * math.sin(theta)
        allowed = max_travel(x, y, dx, dy)
        if abs(step.value) > allowed:
            end_x, end_y = x + abs(step.value) * dx, y + abs(step.value) * dy
            direction = "forward" if step.value > 0 else "backward"
            errors.append(
                f"step {i}: would leave the field at ({end_x:.2f}, {end_y:.2f}); "
                f"at most {allowed:.1f} m {direction} is possible here"
            )
            return
        x += abs(step.value) * dx
        y += abs(step.value) * dy


def validate_plan(raw: Any, start: Pose2D) -> ValidationResult:
    errors: list[str] = []
    steps = _parse_steps(raw, errors)
    if errors:
        return ValidationResult(errors=errors)
    steps = split_turns(steps)
    _check_bounds(steps, start, errors)
    if errors:
        return ValidationResult(errors=errors)
    return ValidationResult(steps=steps)

import math

import pytest

from nl_turtle.plan import Pose2D, Step
from nl_turtle.planner import PlannerError, extract_json
from nl_turtle.validator import MAX_STEPS, split_turns, validate_plan

CENTER = Pose2D(5.5, 5.5, 0.0)


def test_valid_triangle_passes() -> None:
    raw = {"steps": [{"type": "forward", "value": 2}, {"type": "turn", "value": 120}] * 3}
    result = validate_plan(raw, CENTER)
    assert result.ok, result.errors
    assert result.steps[0] == Step("forward", 2.0)
    assert all(abs(s.value) <= 90 for s in result.steps if s.type == "turn")


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({}, '"steps" list'),
        ({"steps": []}, "empty"),
        ({"steps": [{"type": "jump", "value": 1}]}, "unknown type"),
        ({"steps": [{"type": "forward", "value": "2"}]}, "finite number"),
        ({"steps": [{"type": "forward", "value": float("nan")}]}, "finite number"),
        ({"steps": [{"type": "forward", "value": True}]}, "finite number"),
        ({"steps": [{"type": "forward", "value": 9}]}, "forward must be"),
        ({"steps": [{"type": "forward", "value": -9}]}, "forward must be"),
        ({"steps": [{"type": "turn", "value": 720}]}, "turn must be"),
        ({"steps": [{"type": "forward", "value": 1}] * (MAX_STEPS + 1)}, "too many steps"),
        ({"steps": [{"type": "turn", "value": 0}]}, "no effective steps"),
    ],
)
def test_broken_plans_are_rejected(raw: object, fragment: str) -> None:
    result = validate_plan(raw, CENTER)
    assert not result.ok
    assert any(fragment in e for e in result.errors), result.errors


def test_plan_leaving_field_is_rejected() -> None:
    raw = {"steps": [{"type": "forward", "value": 4}, {"type": "forward", "value": 4}]}
    result = validate_plan(raw, CENTER)
    assert not result.ok
    assert "leave the field" in result.errors[0]


def test_zero_padding_steps_are_dropped() -> None:
    # Regression: Gemini answered "go straight 2 m" with a trailing 0-degree turn.
    raw = {"steps": [{"type": "forward", "value": 2.0}, {"type": "turn", "value": 0}]}
    result = validate_plan(raw, CENTER)
    assert result.ok, result.errors
    assert result.steps == [Step("forward", 2.0)]


def test_backward_is_allowed_and_bounds_checked() -> None:
    assert validate_plan({"steps": [{"type": "forward", "value": -2}]}, CENTER).ok
    near_left_wall = Pose2D(1.5, 5.5, 0.0)
    result = validate_plan({"steps": [{"type": "forward", "value": -2}]}, near_left_wall)
    assert not result.ok
    assert "at most 1.0 m backward" in result.errors[0]


def test_rejection_reports_remaining_distance() -> None:
    # Regression: at x≈6.5 facing +x, "go straight 5 m" must fail and say how far is possible.
    pose = Pose2D(6.53, 5.52, 0.0)
    result = validate_plan({"steps": [{"type": "forward", "value": 5}]}, pose)
    assert not result.ok
    assert "at most 4.0 m forward" in result.errors[0]


def test_bounds_follow_heading() -> None:
    facing_up = Pose2D(5.5, 9.0, math.pi / 2)
    assert not validate_plan({"steps": [{"type": "forward", "value": 2}]}, facing_up).ok
    assert validate_plan({"steps": [{"type": "turn", "value": 180}, {"type": "forward", "value": 2}]}, facing_up).ok


def test_full_rotation_is_split_into_quarter_turns() -> None:
    assert split_turns([Step("turn", 360.0)]) == [Step("turn", 90.0)] * 4
    assert split_turns([Step("turn", -135.0)]) == [Step("turn", -90.0), Step("turn", -45.0)]


def test_extract_json_handles_code_fences() -> None:
    text = '```json\n{"steps": [{"type": "turn", "value": 90}]}\n```'
    assert extract_json(text) == {"steps": [{"type": "turn", "value": 90}]}


def test_extract_json_rejects_prose() -> None:
    with pytest.raises(PlannerError):
        extract_json("I cannot do that.")

import math
from dataclasses import dataclass
from typing import Literal

StepType = Literal["forward", "turn"]


@dataclass(frozen=True)
class Step:
    """forward: value is meters. turn: value is degrees, positive = counter-clockwise."""

    type: StepType
    value: float


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    theta: float


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))

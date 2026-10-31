import math

from geometry_msgs.msg import Twist
from rclpy.node import Node
from turtlesim.msg import Pose

from nl_turtle.plan import Pose2D, Step, normalize_angle

CONTROL_HZ = 50.0
MAX_LINEAR = 2.0
MAX_ANGULAR = 2.0
GAIN_LINEAR = 2.0
GAIN_ANGULAR = 4.0
DIST_TOLERANCE = 0.01
ANGLE_TOLERANCE = 0.005
STEP_TIMEOUT_SEC = 15.0


def clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


class StepExecutor(Node):
    """Runs a list of Steps on turtlesim, closing the loop on /turtle1/pose."""

    def __init__(self, node_name: str = "step_executor") -> None:
        super().__init__(node_name)
        self._steps: list[Step] = []
        self._index = 0
        self._pose: Pose | None = None
        self._start: Pose | None = None
        self._step_started_at = 0.0
        # Cumulative heading goal so per-turn tolerance errors do not stack up.
        self._heading_goal: float | None = None
        self.done = True
        self.aborted = False

        self._cmd_pub = self.create_publisher(Twist, "/turtle1/cmd_vel", 10)
        self.create_subscription(Pose, "/turtle1/pose", self._on_pose, 10)
        self.create_timer(1.0 / CONTROL_HZ, self._on_timer)

    @property
    def pose(self) -> Pose2D | None:
        if self._pose is None:
            return None
        return Pose2D(self._pose.x, self._pose.y, self._pose.theta)

    def start(self, steps: list[Step]) -> None:
        self._steps = list(steps)
        self._index = 0
        self._start = None
        self._heading_goal = None
        self.aborted = False
        self.done = not self._steps

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _on_pose(self, msg: Pose) -> None:
        self._pose = msg

    def _on_timer(self) -> None:
        if self.done or self._pose is None:
            return
        if self._index >= len(self._steps):
            self._finish("all steps finished")
            return

        step = self._steps[self._index]
        if self._start is None:
            self._start = self._pose
            self._step_started_at = self._now()
            if self._heading_goal is None:
                self._heading_goal = self._pose.theta
            if step.type == "turn":
                self._heading_goal = normalize_angle(self._heading_goal + math.radians(step.value))
            self.get_logger().info(f"step {self._index + 1}/{len(self._steps)}: {step.type} {step.value:g}")

        if self._now() - self._step_started_at > STEP_TIMEOUT_SEC:
            self.aborted = True
            self._finish(f"step {self._index + 1} timed out after {STEP_TIMEOUT_SEC:.0f}s; stopping")
            return

        finished = self._drive_forward(step.value) if step.type == "forward" else self._drive_turn()
        if finished:
            self._stop()
            self._start = None
            self._index += 1

    def _finish(self, message: str) -> None:
        self._stop()
        self.done = True
        log = self.get_logger().warn if self.aborted else self.get_logger().info
        log(message)

    def _drive_forward(self, distance: float) -> bool:
        assert self._start is not None and self._pose is not None
        travelled = math.hypot(self._pose.x - self._start.x, self._pose.y - self._start.y)
        remaining = abs(distance) - travelled
        if remaining <= DIST_TOLERANCE:
            return True
        cmd = Twist()
        cmd.linear.x = math.copysign(min(MAX_LINEAR, GAIN_LINEAR * remaining), distance)
        self._cmd_pub.publish(cmd)
        return False

    def _drive_turn(self) -> bool:
        assert self._heading_goal is not None and self._pose is not None
        error = normalize_angle(self._heading_goal - self._pose.theta)
        if abs(error) <= ANGLE_TOLERANCE:
            return True
        cmd = Twist()
        cmd.angular.z = clamp(GAIN_ANGULAR * error, MAX_ANGULAR)
        self._cmd_pub.publish(cmd)
        return False

    def _stop(self) -> None:
        self._cmd_pub.publish(Twist())

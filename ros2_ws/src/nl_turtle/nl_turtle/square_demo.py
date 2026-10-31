import rclpy

from nl_turtle.motion import StepExecutor
from nl_turtle.plan import Step

SIDE_METERS = 2.0


def square_plan(side: float = SIDE_METERS) -> list[Step]:
    return [Step("forward", side), Step("turn", 90.0)] * 4


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = StepExecutor(node_name="square_demo")
    node.start(square_plan())
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

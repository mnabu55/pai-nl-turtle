import json
import sys
import time
from pathlib import Path

import rclpy

from nl_turtle.motion import StepExecutor
from nl_turtle.plan import Pose2D
from nl_turtle.planner import PlannerError, load_dotenv, plan_from_instruction
from nl_turtle.validator import validate_plan

POSE_WAIT_SEC = 10.0


def find_env_file() -> Path | None:
    """Look for .env from the current directory and from the (symlink-resolved) source tree upward."""
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        for directory in (base, *base.parents):
            candidate = directory / ".env"
            if candidate.is_file():
                return candidate
    return None


def refresh_pose(node: StepExecutor, timeout: float) -> Pose2D | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    return node.pose


def wait_for_pose(node: StepExecutor) -> Pose2D:
    deadline = time.monotonic() + POSE_WAIT_SEC
    while node.pose is None and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if node.pose is None:
        raise RuntimeError("no /turtle1/pose received; is turtlesim_node running?")
    return node.pose


def handle_instruction(node: StepExecutor, instruction: str) -> bool:
    pose = refresh_pose(node, timeout=0.3) or wait_for_pose(node)
    print(f"\n[指示] {instruction}")
    print("[AI] Geminiで手順を生成中...")
    started = time.monotonic()
    try:
        raw = plan_from_instruction(instruction, pose)
    except PlannerError as exc:
        print(f"[AI] 失敗: {exc}")
        return False
    print(f"[AI] {time.monotonic() - started:.1f}秒  出力: {json.dumps(raw, ensure_ascii=False)}")

    result = validate_plan(raw, pose)
    if not result.ok:
        print("[検証] NG → 実行しません")
        for error in result.errors:
            print(f"  - {error}")
        return False
    print(f"[検証] OK ({len(result.steps)}ステップ)")

    node.start(result.steps)
    while rclpy.ok() and not node.done:
        rclpy.spin_once(node, timeout_sec=0.05)
    print("[実行] 中断しました" if node.aborted else "[実行] 完了")
    return not node.aborted


def main(args: list[str] | None = None) -> None:
    # Keep our console lines in order with ROS log lines when stdout is piped or recorded.
    sys.stdout.reconfigure(line_buffering=True)
    env_file = find_env_file()
    if env_file is not None:
        load_dotenv(env_file)

    rclpy.init(args=args)
    node = StepExecutor(node_name="nl_commander")
    try:
        wait_for_pose(node)
        cli_args = rclpy.utilities.remove_ros_args(sys.argv)[1:]
        if cli_args:
            ok = handle_instruction(node, " ".join(cli_args))
            sys.exit(0 if ok else 1)
        print("日本語で指示を入力してください（終了は q）")
        while rclpy.ok():
            try:
                instruction = input("> ").strip()
            except EOFError:
                break
            if instruction in ("q", "quit", "exit"):
                break
            if instruction:
                handle_instruction(node, instruction)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

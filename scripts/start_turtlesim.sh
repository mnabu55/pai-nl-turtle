#!/usr/bin/env bash
# Open the turtlesim window on the browser desktop (http://localhost:6080).
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose exec -d -u ubuntu -e DISPLAY=:1 sim \
  bash -lc 'source /opt/ros/humble/setup.bash && ros2 run turtlesim turtlesim_node'
echo "turtlesim started. Open http://localhost:${VNC_PORT:-6080} to see it."

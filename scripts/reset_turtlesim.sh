#!/usr/bin/env bash
# Put the turtle back in the center and clear the drawing.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose exec -T -u ubuntu sim \
  bash -lc 'source /opt/ros/humble/setup.bash && ros2 service call /reset std_srvs/srv/Empty' >/dev/null
echo "turtlesim reset."

#!/usr/bin/env bash
# Give instructions in natural language from the host terminal (so the host's Japanese IME works).
#   scripts/commander.sh                      interactive mode, type "q" to quit
#   scripts/commander.sh "一辺2mの正方形を描いて"   run one instruction and exit
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "error: .env not found. Copy .env.example to .env and set GEMINI_API_KEY." >&2
  exit 1
fi

docker compose exec -u ubuntu -e LANG=C.UTF-8 sim bash -lc '
  set -e
  source /opt/ros/humble/setup.bash
  cd ~/pai-nl-turtle/ros2_ws
  if [[ ! -f install/setup.bash ]]; then
    colcon build --symlink-install >/dev/null
  fi
  source install/setup.bash
  cd ~/pai-nl-turtle
  ros2 run nl_turtle nl_commander "$@"
' _ "$@"

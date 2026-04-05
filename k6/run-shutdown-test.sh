#!/bin/bash
set -uo pipefail

TARGET_HOST="${TARGET_HOST:-192.168.55.114}"
SERVER_HOST="${SERVER_HOST:-192.168.55.114}"
RESULT_DIR="./results/shutdown-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULT_DIR"

SERVERS=(
  "python-fastapi-sync:8001:sync-async-lab-python-fastapi-sync-1"
  "python-fastapi-async:8002:sync-async-lab-python-fastapi-async-1"
  "java-spring-mvc:8006:sync-async-lab-java-spring-mvc-1"
  "java-spring-virtual:8008:sync-async-lab-java-spring-virtual-1"
  "go-server:8009:sync-async-lab-go-server-1"
  "node-server:8010:sync-async-lab-node-server-1"
)

echo "=========================================="
echo " Graceful Shutdown Test"
echo " k6 Target: ${TARGET_HOST}"
echo " Docker Host: ${SERVER_HOST}"
echo "=========================================="

for entry in "${SERVERS[@]}"; do
  IFS=':' read -r server port container <<< "$entry"

  echo ""
  echo "--- Testing: ${server} (port ${port}, container ${container}) ---"

  curl -sf "http://${TARGET_HOST}:${port}/io" > /dev/null 2>&1 || {
    echo "SKIP: ${server} not responding"
    continue
  }

  echo "Starting k6 load..."
  k6 run \
    -e "TARGET_HOST=${TARGET_HOST}" \
    -e "TARGET_PORT=${port}" \
    --summary-export="${RESULT_DIR}/${server}.json" \
    "./scenarios/shutdown-test.js" \
    2>&1 | tee "${RESULT_DIR}/${server}.log" &
  K6_PID=$!

  echo "Waiting 20s for load to stabilize..."
  sleep 20

  echo "Sending docker stop (graceful, 10s timeout)..."
  ssh "${SERVER_HOST}" "docker stop --time=10 ${container}" 2>&1

  echo "Waiting for k6 to finish..."
  wait $K6_PID || true

  echo "Restarting container..."
  ssh "${SERVER_HOST}" "docker start ${container}" 2>&1
  sleep 10

  echo "--- Done: ${server} ---"
done

echo ""
echo "=========================================="
echo " All shutdown tests complete. Results in: ${RESULT_DIR}"
echo "=========================================="

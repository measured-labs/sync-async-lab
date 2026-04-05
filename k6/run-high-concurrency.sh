#!/bin/bash
set -uo pipefail

TARGET_HOST="${TARGET_HOST:-192.168.55.114}"
RESULT_DIR="./results/high-concurrency-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULT_DIR"

SERVERS=(
  "python-fastapi-sync:8001"
  "python-fastapi-async:8002"
  "python-django-sync:8003"
  "python-django-async-raw:8005"
  "java-spring-mvc:8006"
  "java-spring-webflux:8007"
  "java-spring-virtual:8008"
  "go-server:8009"
)

echo "=========================================="
echo " High Concurrency I/O Test (500→1000 VU)"
echo " Target: ${TARGET_HOST}"
echo " Results: ${RESULT_DIR}"
echo "=========================================="

for entry in "${SERVERS[@]}"; do
  server="${entry%%:*}"
  port="${entry##*:}"

  echo ""
  echo "--- Warming up: ${server} (port ${port}) ---"
  curl -sf "http://${TARGET_HOST}:${port}/io" > /dev/null 2>&1 || {
    echo "SKIP: ${server} is not responding on port ${port}"
    continue
  }
  sleep 2

  echo ""
  echo ">>> Running high-concurrency-io on ${server} (port ${port})"
  echo "-------------------------------------------"

  k6 run \
    -e "TARGET_HOST=${TARGET_HOST}" \
    -e "TARGET_PORT=${port}" \
    --summary-export="${RESULT_DIR}/${server}.json" \
    "./scenarios/high-concurrency-io.js" \
    2>&1 | tee "${RESULT_DIR}/${server}.log" || true

  echo "--- Cooldown 15s ---"
  sleep 15
done

echo ""
echo "=========================================="
echo " All tests complete. Results in: ${RESULT_DIR}"
echo "=========================================="

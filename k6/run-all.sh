#!/bin/bash
set -uo pipefail

TARGET_HOST="${TARGET_HOST:-192.168.55.114}"
RESULT_DIR="./results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULT_DIR"

SERVERS=(
  "python-fastapi-sync:8001"
  "python-fastapi-async:8002"
  "python-django-sync:8003"
  "python-django-async:8004"
  "python-django-async-raw:8005"
  "java-spring-mvc:8006"
  "java-spring-webflux:8007"
  "java-spring-virtual:8008"
  "go-server:8009"
)

SCENARIOS=("io-bound" "cpu-bound")

echo "=========================================="
echo " sync-async-lab k6 benchmark runner"
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

  for scenario in "${SCENARIOS[@]}"; do
    echo ""
    echo ">>> Running ${scenario} on ${server} (port ${port})"
    echo "-------------------------------------------"

    k6 run \
      -e "TARGET_HOST=${TARGET_HOST}" \
      -e "TARGET_PORT=${port}" \
      --summary-export="${RESULT_DIR}/${server}-${scenario}.json" \
      "./scenarios/${scenario}.js" \
      2>&1 | tee "${RESULT_DIR}/${server}-${scenario}.log" || true

    echo "--- Cooldown 10s ---"
    sleep 10
  done
done

echo ""
echo "=========================================="
echo " All tests complete. Results in: ${RESULT_DIR}"
echo "=========================================="

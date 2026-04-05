#!/bin/bash
set -uo pipefail

RESULT_DIR="./results/memory-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULT_DIR"
OUTFILE="${RESULT_DIR}/docker-stats.csv"

echo "timestamp,container,cpu_pct,mem_usage,mem_limit,mem_pct,net_in,net_out" > "$OUTFILE"

echo "Collecting docker stats every 5s for 3 minutes..."
echo "Results: ${OUTFILE}"

for i in $(seq 1 36); do
  ts=$(date +%Y-%m-%dT%H:%M:%S)
  docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}}" | while read line; do
    echo "${ts},${line}" >> "$OUTFILE"
  done
  sleep 5
done

echo "Collection complete. Results in: ${OUTFILE}"

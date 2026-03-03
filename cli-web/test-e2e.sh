#!/usr/bin/env bash
set -euo pipefail

BIN=./cli-web
export DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.colima/default/docker.sock}"

echo "=== E2E: create bash session ==="
OUTPUT=$($BIN create --tool bash)
echo "$OUTPUT"
SID=$(echo "$OUTPUT" | grep '^session:' | awk '{print $2}')
echo "Parsed session ID: $SID"

echo "=== E2E: exec ls /workspace ==="
$BIN exec "$SID" -- ls /workspace

echo "=== E2E: exec echo hello ==="
$BIN exec "$SID" -- echo hello

echo "=== E2E: check MEMORY_DIR env ==="
$BIN exec "$SID" -- printenv MEMORY_DIR

echo "=== E2E: check uv installed ==="
$BIN exec "$SID" -- uv --version

echo "=== E2E: list sessions ==="
$BIN list

echo "=== E2E: stop session ==="
$BIN stop "$SID"

echo "=== E2E: remove session ==="
$BIN remove "$SID"

echo "=== E2E: PASS ==="

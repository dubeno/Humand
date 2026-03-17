#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose down -v --remove-orphans
rm -rf data logs

printf 'Humand demo state has been cleared.\n'
printf 'Run `make demo` to start again from a fresh local inbox.\n'

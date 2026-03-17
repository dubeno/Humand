#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env && -f env.example ]]; then
  cp env.example .env
  printf 'Created .env from env.example for the local demo.\n'
fi

printf 'Starting the Humand local demo stack...\n'
printf 'The simulator inbox will be available at http://localhost:5000 once the services are healthy.\n'

docker compose up --build

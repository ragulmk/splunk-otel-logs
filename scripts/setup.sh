#!/usr/bin/env bash
# Creates .env with a random Splunk password and HEC token (never committed).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  echo ".env already exists, leaving it unchanged."
  exit 0
fi

uuid() { python3 -c 'import uuid; print(uuid.uuid4())'; }
password="Spl-$(uuid | cut -c1-13)"

sed -e "s/^SPLUNK_PASSWORD=.*/SPLUNK_PASSWORD=${password}/" \
    -e "s/^SPLUNK_HEC_TOKEN=.*/SPLUNK_HEC_TOKEN=$(uuid)/" \
    .env.example > .env

echo "Created .env"
echo "  Splunk login: admin / ${password}"

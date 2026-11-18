#!/usr/bin/env bash
# Sends one event straight to Splunk HEC to verify the token and index work.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .env

curl -sk "https://localhost:8088/services/collector/event" \
  -H "Authorization: Splunk ${SPLUNK_HEC_TOKEN}" \
  -d '{"index":"app_logs","sourcetype":"app:json","event":{"level":"INFO","service":"hec-test","msg":"hello from send-test-event.sh"}}'
echo
echo "Now search in Splunk:  index=app_logs service=hec-test"

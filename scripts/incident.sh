#!/usr/bin/env bash
# Start a simulated incident in the log generator.
#   ./scripts/incident.sh payment_outage 600   razorpay starts timing out (10 min)
#   ./scripts/incident.sh brute_force 300      attackers hammer /api/login (5 min)
#   ./scripts/incident.sh slow_db 600          orders-service database becomes slow
#   ./scripts/incident.sh stop                 end all incidents
set -euo pipefail
CONTROL_DIR="$(dirname "$0")/../control"
name="${1:-}"
seconds="${2:-600}"

case "$name" in
  payment_outage|brute_force|slow_db)
    echo $(( $(date +%s) + seconds )) > "$CONTROL_DIR/$name"
    echo "Incident '$name' running for ${seconds}s. Watch the Splunk dashboards."
    ;;
  stop)
    rm -f "$CONTROL_DIR"/payment_outage "$CONTROL_DIR"/brute_force "$CONTROL_DIR"/slow_db
    echo "All incidents stopped."
    ;;
  *)
    echo "usage: $0 {payment_outage|brute_force|slow_db} [seconds] | stop" >&2
    exit 1
    ;;
esac

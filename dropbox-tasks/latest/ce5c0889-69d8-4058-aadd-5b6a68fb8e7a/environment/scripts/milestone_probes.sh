#!/bin/bash
set -euo pipefail
MODE="${1:-}"
case "$MODE" in
  ledgers)
    deskctl ledgers
    ;;
  referee)
    deskctl referee
    ;;
  verdicts)
    deskctl verdicts
    ;;
  combos)
    deskctl combos
    ;;
  seal)
    deskctl seal
    ;;
  rules)
    deskctl rules
    ;;
  fw)
    deskctl fw
    ;;
  *)
    echo "usage: milestone_probes.sh ledgers|referee|verdicts|combos|seal|rules|fw" >&2
    exit 1
    ;;
esac

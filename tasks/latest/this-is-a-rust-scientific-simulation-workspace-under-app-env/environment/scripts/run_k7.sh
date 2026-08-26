#!/usr/bin/env bash
set -euo pipefail
DELIM=$(awk -F'\t' '$1=="TICK_DELIM"{print $2; exit}' /app/environment/docs/lex_k.tsv)
SUITE="g2"
TICKS="12:0"
EMIT=""
MODE="run"
while [[ $# -gt 0 ]]; do
  case "$1" in
    probe) MODE="probe"; shift ;;
    --suite) SUITE="$2"; shift 2 ;;
    --ticks)
      TICKS="$2"
      if [[ "$TICKS" != *"$DELIM"* ]]; then
        TICKS="${TICKS}${DELIM}0"
      fi
      shift 2
      ;;
    --emit) EMIT="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ "$MODE" == "probe" ]]; then
  exec /app/bin/k7 probe --suite "$SUITE"
fi
if [[ -n "$EMIT" ]]; then
  exec /app/bin/k7 --suite "$SUITE" --ticks "$TICKS" --emit "$EMIT"
fi
exec /app/bin/k7 --suite "$SUITE" --ticks "$TICKS"

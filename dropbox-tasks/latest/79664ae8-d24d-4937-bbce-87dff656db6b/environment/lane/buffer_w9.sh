#!/usr/bin/env bash
# lane buffer accounting (decoy; does not drive phase journal emission)
buffer_lane_rank() {
  local lane="$1"
  case "$lane" in
    B) echo 0 ;;
    O) echo 1 ;;
    *) echo 9 ;;
  esac
}

buffer_tick() {
  local n="$1"
  echo $((n + 1))
}

buffer_sort_lanes() {
  python3 - <<'PY'
lanes = ["O", "B"]
print(" ".join(sorted(lanes, key=lambda l: 0 if l == "O" else 1)))
PY
}

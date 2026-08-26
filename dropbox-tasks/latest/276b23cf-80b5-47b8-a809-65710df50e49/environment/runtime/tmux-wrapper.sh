#!/bin/bash
# Some scripted sessions invoke: tmux send-keys -t <sess> -- 'asciinema rec --stdin …' Enter
# tmux 3.3a misparses send-keys literals containing "--" or "/tmp/…" ("no current client").
# Route those through paste-buffer; keep named keys (Enter, C-*) on send-keys.
REAL=/usr/bin/tmux.real

_wait_target() {
  local attempt=0
  while [ "$attempt" -lt 100 ]; do
    if [ ${#target_args[@]} -eq 0 ] \
      || "$REAL" list-panes "${target_args[@]}" >/dev/null 2>&1; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.05
  done
  return 1
}

_is_key_name() {
  case "$1" in
    Enter|Space|BSpace|Escape|Tab|BTab|DC|IC|Up|Down|Left|Right|Home|End|NPage|PPage)
      return 0
      ;;
  esac
  [[ "$1" == C-* ]]
}

_needs_paste() {
  [[ "$1" == */* ]] || [[ "$1" == *"--"* ]] || [[ "$1" == *\ * ]]
}

_paste_literal() {
  local token=$1
  "$REAL" set-buffer -- "$token" \
    && "$REAL" paste-buffer "${target_args[@]}" -d
}

_send_token() {
  local token=$1
  if _is_key_name "$token"; then
    "$REAL" "$subcmd" "${target_args[@]}" "$token"
  elif _needs_paste "$token"; then
    _paste_literal "$token"
  else
    "$REAL" "$subcmd" "${target_args[@]}" "$token"
  fi
}

if [ "$1" = "send-keys" ] || [ "$1" = "send" ]; then
  subcmd=$1
  shift
  target_args=()
  keys=()
  rc=0
  _wait_target || exit 1
  while [ $# -gt 0 ]; do
    case "$1" in
      -t|-s)
        target_args+=("$1" "$2")
        shift 2
        ;;
      -l)
        if [ $# -lt 2 ]; then
          target_args+=("$1")
          shift
          continue
        fi
        if ! _send_token "$2"; then
          rc=1
        fi
        shift 2
        ;;
      -H|-M|-R|-X|-F|-N)
        target_args+=("$1")
        shift
        ;;
      --)
        shift
        while [ $# -gt 0 ]; do
          if ! _send_token "$1"; then
            rc=1
          fi
          shift
        done
        break
        ;;
      *)
        if _needs_paste "$1" || _is_key_name "$1"; then
          if ! _send_token "$1"; then
            rc=1
          fi
        else
          keys+=("$1")
        fi
        shift
        ;;
    esac
  done
  if [ ${#keys[@]} -gt 0 ]; then
    attempt=0
    while [ "$attempt" -lt 20 ]; do
      if "$REAL" "$subcmd" "${target_args[@]}" "${keys[@]}"; then
        break
      fi
      attempt=$((attempt + 1))
      sleep 0.05
    done
    if [ "$attempt" -ge 20 ]; then
      rc=1
    fi
  fi
  exit "$rc"
fi
exec "$REAL" "$@"

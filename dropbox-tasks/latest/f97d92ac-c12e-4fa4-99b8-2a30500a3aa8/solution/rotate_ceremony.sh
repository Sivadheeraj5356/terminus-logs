#!/usr/bin/env bash
set -uo pipefail

policy=/app/ceremony/policy.json
output=/app/ceremony/rotation-attestation.json
seen_policy=0
seen_output=0

fail() {
    rm -f -- "$output" 2>/dev/null || true
    printf 'rotate_ceremony: %s\n' "$1" >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --policy)
            [ "$seen_policy" -eq 0 ] || fail "--policy may be specified only once"
            [ "$#" -ge 2 ] || fail "--policy requires a path"
            policy=$2
            seen_policy=1
            shift 2
            ;;
        --output)
            [ "$seen_output" -eq 0 ] || fail "--output may be specified only once"
            [ "$#" -ge 2 ] || fail "--output requires a path"
            output=$2
            seen_output=1
            shift 2
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

if ! rm -f -- "$output"; then
    fail "cannot remove stale output"
fi

output_dir=$(dirname -- "$output")
[ -d "$output_dir" ] || fail "output directory does not exist"

stage=$(mktemp "${output}.tmp.XXXXXX") || fail "cannot create staged output"
cleanup() {
    rm -f -- "$stage"
}
trap cleanup EXIT HUP INT TERM

if ! /usr/bin/python3 /app/bin/.rotate_token.py "$policy" "$stage"; then
    exit 2
fi

key_path=$(jq -er '.active.private_key_path' "$policy" 2>/dev/null) || fail "validated policy could not be reread"
if [ -e "$key_path" ]; then
    if ! shred -u -- "$key_path"; then
        fail "could not remove the staged private key"
    fi
fi

if ! mv -f -- "$stage" "$output"; then
    fail "could not commit the attestation"
fi
trap - EXIT HUP INT TERM

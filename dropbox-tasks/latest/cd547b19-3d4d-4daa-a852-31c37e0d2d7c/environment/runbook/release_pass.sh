#!/usr/bin/env bash
set -euo pipefail

MATRIX=${1:-/app/environment/profiles/public.matrix}
OUT=${2:-/app/output/sdk-abi-index}
ENV_ROOT=${SDK_ENV_ROOT:-/app/environment}
BUILD_ROOT=${SDK_BUILD_ROOT:-/app/build/sdk-abi-index}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=cache_stamp.sh
source "$SCRIPT_DIR/cache_stamp.sh"
# shellcheck source=label_journal.sh
source "$SCRIPT_DIR/label_journal.sh"

mkdir -p "$OUT" "$BUILD_ROOT"
: > "$OUT/probe.jsonl"
: > "$OUT/.lane-records.jsonl"
printf 'phase\tlane\tpath\tdetail\n' > "$OUT/trace.tsv"

matrix_abs=$(cd "$(dirname "$MATRIX")" && pwd)/$(basename "$MATRIX")
matrix_dir=$(dirname "$matrix_abs")
matrix_sha=$(sha256_file "$matrix_abs")
idl_digest_value=$(bash "$SCRIPT_DIR/idl_fingerprint.sh" "$ENV_ROOT")
tool_digest_value=$(bash "$SCRIPT_DIR/tool_fingerprint.sh" "$ENV_ROOT")

while read -r lane profile_ref extra; do
  if [[ -z "${lane:-}" || "${lane:0:1}" == "#" ]]; then
    continue
  fi
  if [[ -n "${extra:-}" ]]; then
    echo "invalid matrix row for $lane: too many columns" >&2
    exit 2
  fi

  profile_path=$(resolve_profile_path "$matrix_dir" "$profile_ref" "$ENV_ROOT")
  if [[ ! -f "$profile_path" ]]; then
    echo "profile not found: $profile_ref" >&2
    exit 2
  fi
  profile_abs=$(cd "$(dirname "$profile_path")" && pwd)/$(basename "$profile_path")
  profile_sha=$(sha256_file "$profile_abs")
  bdir="$BUILD_ROOT/$lane"
  mkdir -p "$bdir"
  stamp_file="$bdir/.sdk-profile.stamp"
  journal_file=$(lane_journal_path "$bdir")

  printf 'configure\t%s\t%s\t%s\n' "$lane" "$bdir" "$profile_abs" >> "$OUT/trace.tsv"
  needs_configure=1
  if [[ -f "$bdir/build.ninja" ]] && stamp_keep "$stamp_file" "$profile_abs"; then
    if journal_fresh "$journal_file" "$idl_digest_value" "$tool_digest_value"; then
      needs_configure=0
    fi
  fi

  needs_regenerate=0
  if [[ "$needs_configure" -eq 1 ]]; then
    cmake -S "$ENV_ROOT" -B "$bdir" -G Ninja \
      -DSDK_LANE_FILE="$profile_abs" \
      -DSDK_LANE_LABEL="$lane" >/dev/null
    stamp_write "$stamp_file" "$profile_abs"
    configure_epoch=$(next_configure_epoch "$journal_file")
    needs_regenerate=1
  else
    configure_epoch=$(read_configure_epoch "$journal_file")
  fi

  header_path="$bdir/generated/include/generated/sdk.hpp"
  layout_src="$bdir/generated/sdk.layout.json"
  # Prefer the checked-in preview when the lane header is absent.
  if [[ ! -f "$header_path" ]]; then
    header_path="$ENV_ROOT/include/generated/sdk.hpp"
    layout_src="$ENV_ROOT/abi/preview.layout.json"
  fi

  printf 'build\t%s\t%s\t%s\n' "$lane" "$bdir" "sdk_probe" >> "$OUT/trace.tsv"
  cmake --build "$bdir" --target sdk_probe >/dev/null

  if [[ "$needs_regenerate" -eq 1 ]]; then
    generation_lineage=$(next_generation_lineage "$journal_file")
  else
    generation_lineage=$(read_generation_lineage "$journal_file")
    if [[ "$generation_lineage" -eq 0 ]]; then
      generation_lineage=1
    fi
  fi

  gen_json="$OUT/.$lane.generated.json"
  cmp_json="$OUT/.$lane.compiled.json"

  printf 'header\t%s\t%s\t%s\n' "$lane" "$header_path" "parse" >> "$OUT/trace.tsv"
  cp "$layout_src" "$gen_json"

  printf 'probe\t%s\t%s\t%s\n' "$lane" "$bdir/sdk_probe" "run" >> "$OUT/trace.tsv"
  "$bdir/sdk_probe" > "$cmp_json"

  write_lane_journal \
    "$journal_file" "$lane" "$profile_sha" \
    "$idl_digest_value" "$tool_digest_value" "$matrix_sha" \
    "$configure_epoch" "$generation_lineage"

  jq -n \
    --arg lane "$lane" \
    --arg profile_path "$profile_abs" \
    --arg profile_sha256 "$profile_sha" \
    --argjson configure_epoch "$configure_epoch" \
    --argjson generation_lineage "$generation_lineage" \
    --slurpfile generated "$gen_json" \
    --slurpfile compiled "$cmp_json" \
    '{
      lane: $lane,
      profile_path: $profile_path,
      profile_sha256: $profile_sha256,
      configure_epoch: $configure_epoch,
      generation_lineage: $generation_lineage,
      generated: $generated[0],
      compiled: $compiled[0]
    }' \
    | jq -c 'if ('"$layout_match_filter"') then . + {status:"match"} else . + {status:"mismatch"} end' \
    >> "$OUT/probe.jsonl"

  jq -c -n \
    --arg lane "$lane" \
    --arg path "$profile_abs" \
    --arg sha256 "$profile_sha" \
    --arg generated_digest "$(jq -r '.digest' "$gen_json")" \
    --argjson configure_epoch "$configure_epoch" \
    --argjson generation_lineage "$generation_lineage" \
    '{lane:$lane,path:$path,sha256:$sha256,generated_digest:$generated_digest,configure_epoch:$configure_epoch,generation_lineage:$generation_lineage}' \
    >> "$OUT/.lane-records.jsonl"
done < "$matrix_abs"

bash "$SCRIPT_DIR/emit_artifacts.sh" \
  "$OUT/probe.jsonl" \
  "$OUT/.lane-records.jsonl" \
  "$OUT/manifest.json" \
  "$OUT/provenance.json" \
  "$OUT/loader_journal.tsv" \
  "$matrix_abs" \
  "$matrix_sha" \
  "$ENV_ROOT" \
  "$BUILD_ROOT"

rm -f "$OUT"/.*.generated.json "$OUT"/.*.compiled.json "$OUT/.lane-records.jsonl"

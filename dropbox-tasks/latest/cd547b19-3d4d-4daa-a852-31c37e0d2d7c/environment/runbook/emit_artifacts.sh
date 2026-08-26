#!/usr/bin/env bash
set -euo pipefail

probe_jsonl=${1:?probe jsonl required}
lane_records=${2:?lane records jsonl required}
manifest_out=${3:?manifest output required}
provenance_out=${4:?provenance output required}
loader_out=${5:?loader journal output required}
matrix_path=${6:?matrix path required}
matrix_sha=${7:?matrix sha required}
env_root=${8:?environment root required}
build_root=${9:?build root required}

jq -s \
  --arg matrix_path "$matrix_path" \
  --arg matrix_sha256 "$matrix_sha" \
  '{schema_version:1,matrix_path:$matrix_path,matrix_sha256:$matrix_sha256,record_count:length,records:.}' \
  "$probe_jsonl" > "$manifest_out"

jq -s \
  --arg env_root "$env_root" \
  --arg build_root "$build_root" \
  --arg matrix_path "$matrix_path" \
  --arg matrix_sha256 "$matrix_sha" \
  '{schema_version:1,environment_root:$env_root,build_root:$build_root,matrix_path:$matrix_path,matrix_sha256:$matrix_sha256,lanes:.}' \
  "$lane_records" > "$provenance_out"

{
  printf 'lane\tphase\tfield\tstatus\tdetail\n'
  jq -r '
    . as $rec
    | $rec.compiled.fields as $c
    | $rec.generated.fields[] as $gf
    | ($c[] | select(.name == $gf.name)) as $cf
    | (if $gf.slot == $cf.slot and $gf.offset == $cf.offset and $gf.size == $cf.size and $gf.ctype == $cf.ctype
       then "accepted" else "rejected" end) as $status
    | [
        $rec.lane,
        (if $gf.slot < 12 then "legacy" else "extension" end),
        $gf.name,
        $status,
        ("slot=" + ($gf.slot | tostring) + " offset=" + ($gf.offset | tostring))
      ] | @tsv
  ' "$probe_jsonl"
} > "$loader_out"

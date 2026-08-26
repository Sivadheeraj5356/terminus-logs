#!/bin/bash
# Reference oracle for the ReefBox calibration-manifest task.
#
# Installs the calibration pipeline the Terraform scaffold invokes, then runs
# `terraform apply` to decode the PNG calibration blocks, merge the YAML model
# cards, and write /app/out/inference_manifest.json.
#
# Ground truth reproduced by this oracle (all conveyed by the field notebook):
#   * PNG tEXt value under key `reefbox:calibration` (fw 2.x) wins over `rbx:cal`
#     (fw 1.x); its value is base64 of a packed big-endian binary blob:
#       "RB" | ver | flags(bits0-1 variant, bits2/3/4 = nz0/1/2) | seq u16 |
#       wb0/1/2 u16 (=round(wb*10000)) | blk0/1/2 u8 | co0/1/2 u8 (skip) |
#       dev_len+dev | site_len+site | CRC-16/CCITT-FALSE(u16) over all prior bytes.
#   * decode/CRC failure -> bad_checksum; no calib chunk -> missing_calibration.
#   * variant A slots {RED:0,GREEN:1,NIR:2}; variant B {RED:2,GREEN:1,NIR:0};
#     variant C -> sensor_variant_c.
#   * per channel: nz=1 -> wb*(255-blk)/255, nz=0 -> wb; round to 6 dp.
#   * site not in global.allowed_sites -> unknown_site.
#   * dedup by device_id: keep highest seq; losers -> superseded.
#   * card merge: model_name/model_version device>site>global; input_size and
#     confidence_threshold site>global only (device ignored); labels_version
#     global only. Devices sorted by device_id; quarantined by source_png.
set -euo pipefail

mkdir -p /app/pipeline

# --- calibration extractor: PNG tEXt -> base64 -> packed binary -> raw fields ---
cat > /app/pipeline/extract_facts.sh <<'EXTRACT_EOF'
#!/usr/bin/env bash
# Pure bash + jq. Emits a JSON array of one record per PNG:
#   {source_png, klass:"missing"} | {..,"bad_checksum"} |
#   {..,"raw", sv, seq, nz[3], wb[3], blk[3], dev, site}
set -euo pipefail
FIX="${1:?fixtures dir}"
JQ="${JQ_BIN:-jq}"

crc16_ok() {  # CRC-16/CCITT-FALSE over all but trailing 2 bytes of a hex string
  local hex="$1" n crc b p k stored
  n=$(( ${#hex} / 2 )); (( n < 3 )) && return 1
  crc=$(( 0xFFFF ))
  for (( p = 0; p < n - 2; p++ )); do
    b=$(( 16#${hex:p*2:2} )); crc=$(( crc ^ (b << 8) ))
    for (( k = 0; k < 8; k++ )); do
      if (( crc & 0x8000 )); then crc=$(( ((crc << 1) ^ 0x1021) & 0xFFFF ));
      else crc=$(( (crc << 1) & 0xFFFF )); fi
    done
  done
  stored=$(( (16#${hex:(n-2)*2:2} << 8) | 16#${hex:(n-1)*2:2} ))
  [ "$crc" -eq "$stored" ]
}

png_text() {  # print the tEXt value for a keyword (empty if absent)
  local f="$1" kw="$2" hex i ln typ total body_hex kwhex j pair this_kw texthex
  hex=$(od -An -v -tx1 "$f" | tr -d ' \n'); i=16
  total=$(( ${#hex} / 2 ))
  while (( i / 2 < total )); do
    ln=$(( 16#${hex:i:8} )); i=$(( i + 8 ))
    typ=$(printf '%b' "\\x${hex:i:2}\\x${hex:i+2:2}\\x${hex:i+4:2}\\x${hex:i+6:2}"); i=$(( i + 8 ))
    body_hex="${hex:i:$(( ln * 2 ))}"
    if [ "$typ" = "tEXt" ]; then
      kwhex=""; j=0
      while (( j < ${#body_hex} )); do
        pair="${body_hex:j:2}"; [ "$pair" = "00" ] && break; kwhex="$kwhex$pair"; j=$(( j + 2 ))
      done
      this_kw=$(printf '%b' "$(echo "$kwhex" | sed 's/\(..\)/\\x\1/g')")
      if [ "$this_kw" = "$kw" ]; then
        texthex="${body_hex:$(( j + 2 ))}"
        printf '%b' "$(echo "$texthex" | sed 's/\(..\)/\\x\1/g')"; return 0
      fi
    fi
    i=$(( i + ln * 2 + 8 )); [ "$typ" = "IEND" ] && break
  done
}

records="[]"
for png in "$FIX"/*.png; do
  pv=$(basename "$png")
  b64=$(png_text "$png" "reefbox:calibration" || true)
  [ -z "$b64" ] && b64=$(png_text "$png" "rbx:cal" || true)
  if [ -z "$b64" ]; then
    records=$("$JQ" --arg p "$pv" '. + [{source_png:$p, klass:"missing"}]' <<<"$records"); continue
  fi
  hex=$(printf '%s' "$b64" | base64 -d 2>/dev/null | od -An -v -tx1 | tr -d ' \n' || true)
  if [ -z "$hex" ] || (( ${#hex} < 44 )) || [ "${hex:0:4}" != "5242" ] || ! crc16_ok "$hex"; then
    records=$("$JQ" --arg p "$pv" '. + [{source_png:$p, klass:"bad_checksum"}]' <<<"$records"); continue
  fi
  flags=$(( 16#${hex:6:2} ))
  case $(( flags & 3 )) in 0) sv=A;; 1) sv=B;; *) sv=C;; esac
  nz0=$(( (flags >> 2) & 1 )); nz1=$(( (flags >> 3) & 1 )); nz2=$(( (flags >> 4) & 1 ))
  seq=$(( 16#${hex:8:4} ))
  wb0=$(( 16#${hex:12:4} )); wb1=$(( 16#${hex:16:4} )); wb2=$(( 16#${hex:20:4} ))
  blk0=$(( 16#${hex:24:2} )); blk1=$(( 16#${hex:26:2} )); blk2=$(( 16#${hex:28:2} ))
  di=36; dlen=$(( 16#${hex:di:2} )); di=$(( di + 2 ))
  dev=$(printf '%b' "$(echo "${hex:di:$(( dlen * 2 ))}" | sed 's/\(..\)/\\x\1/g')"); di=$(( di + dlen * 2 ))
  slen=$(( 16#${hex:di:2} )); di=$(( di + 2 ))
  site=$(printf '%b' "$(echo "${hex:di:$(( slen * 2 ))}" | sed 's/\(..\)/\\x\1/g')")
  records=$("$JQ" --arg p "$pv" --arg sv "$sv" --argjson seq "$seq" \
    --argjson nz0 "$nz0" --argjson nz1 "$nz1" --argjson nz2 "$nz2" \
    --argjson wb0 "$wb0" --argjson wb1 "$wb1" --argjson wb2 "$wb2" \
    --argjson blk0 "$blk0" --argjson blk1 "$blk1" --argjson blk2 "$blk2" \
    --arg dev "$dev" --arg site "$site" \
    '. + [{source_png:$p, klass:"raw", sv:$sv, seq:$seq, nz:[$nz0,$nz1,$nz2],
           wb:[$wb0,$wb1,$wb2], blk:[$blk0,$blk1,$blk2], dev:$dev, site:$site}]' <<<"$records")
done
printf '%s\n' "$records"
EXTRACT_EOF

# --- manifest reducer: classify + scale + dedup + card-merge ---
cat > /app/pipeline/reduce.jq <<'REDUCE_EOF'
def scale($wb; $blk; $nz):
  ($wb / 10000) as $w
  | if $nz == 1 then (($w * (255 - $blk) / 255) * 1000000 | round / 1000000) else $w end;

{ "A": {"RED":0,"GREEN":1,"NIR":2}, "B": {"RED":2,"GREEN":1,"NIR":0} } as $vmap
| $cards.global.allowed_sites as $allowed
| . as $recs
| ( $recs | map(
      if .klass != "raw" then .
      elif (.sv == "C" or ($vmap[.sv] == null)) then {source_png, klass:"variant_c"}
      else . as $r | ($vmap[.sv]) as $m
        | { source_png, klass:"candidate", device_id:$r.dev, site:$r.site,
            sensor_variant:$r.sv, seq:$r.seq,
            channel_scales: {
              RED:   scale($r.wb[$m.RED];   $r.blk[$m.RED];   $r.nz[$m.RED]),
              GREEN: scale($r.wb[$m.GREEN]; $r.blk[$m.GREEN]; $r.nz[$m.GREEN]),
              NIR:   scale($r.wb[$m.NIR];   $r.blk[$m.NIR];   $r.nz[$m.NIR]) } }
      end)) as $c0
| ( $c0 | map(
      . as $r
      | if .klass == "candidate" and (($allowed | index($r.site)) == null)
        then {source_png, klass:"unknown_site"} else . end)) as $recs2
| [ $recs2[] | select(.klass == "candidate") ] as $cands
| ( $cands | group_by(.device_id) | map(sort_by(.seq) | reverse) ) as $groups
| [ $groups[] | .[0] ]    as $winners
| [ $groups[] | .[1:][] ] as $losers
| ( [ $recs2[]  | select(.klass == "missing")      | {source_png, reason:"missing_calibration"} ]
  + [ $recs2[]  | select(.klass == "bad_checksum")  | {source_png, reason:"bad_checksum"} ]
  + [ $recs2[]  | select(.klass == "variant_c")     | {source_png, reason:"sensor_variant_c"} ]
  + [ $recs2[]  | select(.klass == "unknown_site")  | {source_png, reason:"unknown_site"} ]
  + [ $losers[] | {source_png, reason:"superseded"} ]
  ) | sort_by(.source_png) as $quarantined
| [ $winners[]
    | . as $w
    | ($cards.sites[$w.site] // {})        as $s
    | ($cards.devices[$w.device_id] // {}) as $d
    | $cards.global                         as $g
    | {
        device_id: $w.device_id, site: $w.site, source_png: $w.source_png,
        sensor_variant: $w.sensor_variant, channel_scales: $w.channel_scales,
        model_name:    ($d.model_name // $s.model_name // $g.model_name),
        model_version: ($d.model_version // $s.model_version // $g.model_version),
        # input_size is site>global EXCEPT re-opticed site-bravo falls back to global.
        input_size:    (if $w.site == "site-bravo" then $g.input_size
                        else ($s.input_size // $g.input_size) end),
        confidence_threshold: ($s.confidence_threshold // $g.confidence_threshold),
        # labels_version is global-only EXCEPT pilot sites (site-alpha), which
        # override it from their own site card.
        labels_version: (if ($w.site == "site-alpha" and $s.labels_version)
                         then $s.labels_version else $g.labels_version end)
      }
  ] | sort_by(.device_id) as $devices
| {
    manifest_version: "1.0",
    channel_order: ["RED", "GREEN", "NIR"],
    devices: $devices,
    quarantined: $quarantined,
    summary: { included: ($devices | length), quarantined: ($quarantined | length) }
  }
REDUCE_EOF

# --- orchestrated pipeline: decode -> cards -> reduce -> manifest ---
cat > /app/pipeline/build_manifest.sh <<'BUILD_EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="${FIXTURES_DIR:-/app/data/fixtures}"
CARDS="${CARDS_DIR:-/app/data/modelcards}"
OUT="${OUT_DIR:-/app/out}"
YQ="${YQ_BIN:-yq}"; JQ="${JQ_BIN:-jq}"
mkdir -p "$OUT"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

JQ_BIN="$JQ" bash "$HERE/extract_facts.sh" "$FIX" > "$TMP/records.json"

g=$("$YQ" -o=json '.' "$CARDS/global.yaml")
sites="{}"; for f in "$CARDS"/sites/*.yaml; do k=$(basename "$f" .yaml); v=$("$YQ" -o=json '.' "$f"); sites=$("$JQ" --arg k "$k" --argjson v "$v" '. + {($k):$v}' <<<"$sites"); done
devices="{}"; for f in "$CARDS"/devices/*.yaml; do k=$(basename "$f" .yaml); v=$("$YQ" -o=json '.' "$f"); devices=$("$JQ" --arg k "$k" --argjson v "$v" '. + {($k):$v}' <<<"$devices"); done
cards=$("$JQ" -n --argjson g "$g" --argjson s "$sites" --argjson d "$devices" '{global:$g,sites:$s,devices:$d}')

"$JQ" --argjson cards "$cards" -f "$HERE/reduce.jq" "$TMP/records.json" > "$OUT/inference_manifest.json"
echo "wrote $OUT/inference_manifest.json"
BUILD_EOF

chmod +x /app/pipeline/extract_facts.sh /app/pipeline/build_manifest.sh

cd /app
terraform init -input=false >/dev/null
terraform apply -auto-approve -input=false

echo "oracle: wrote /app/out/inference_manifest.json"
jq -c '.summary' /app/out/inference_manifest.json || true

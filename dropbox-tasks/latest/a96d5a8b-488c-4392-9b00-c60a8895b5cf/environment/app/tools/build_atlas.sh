#!/bin/bash
set -euo pipefail

# Unratified rehearsal draft: the rendering operations below deliberately
# disagree with the signed A-RENDER-71 contract in keeper_journal.md. They must
# be corrected in the release copy; this working script is not a source of canon.

DB_PATH="${1:-/app/state/world.db}"
OUT_DIR="${2:-/app/artifacts}"
WORK_DIR="/app/.build/atlas"
SOURCE_DIR="/app/assets/clues"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$OUT_DIR/thumbnails"
rm -f "$OUT_DIR/thumbnails"/*.png "$OUT_DIR/clue_atlas.png"

mapfile -t CLUES < <(
    sqlite3 -batch -noheader -separator '|' "$DB_PATH" \
        "SELECT id, source, position, rotation, matte FROM clues ORDER BY position"
)

if [[ "${#CLUES[@]}" -ne 9 ]]; then
    echo "expected nine clue records, found ${#CLUES[@]}" >&2
    exit 1
fi

tiles=()
expected_position=1
for row in "${CLUES[@]}"; do
    IFS='|' read -r clue_id source position rotation matte <<<"$row"
    if [[ "$position" -ne "$expected_position" ]]; then
        echo "clue positions are not a complete 1..9 sequence" >&2
        exit 1
    fi
    if [[ ! "$source" =~ ^[a-z_]+\.ppm$ ]] || [[ ! -f "$SOURCE_DIR/$source" ]]; then
        echo "invalid clue source for $clue_id" >&2
        exit 1
    fi

    tile="$WORK_DIR/$(printf '%02d' "$position")-$clue_id.png"
    convert "$SOURCE_DIR/$source" \
        -colorspace sRGB \
        -filter triangle \
        -resize 40x40 \
        -background "$matte" \
        -gravity northwest \
        -extent 64x64 \
        -rotate "$rotation" \
        -gravity center \
        -crop 64x64+0+0 +repage \
        -strip \
        -define png:exclude-chunk=date,time \
        -define png:compression-level=9 \
        "PNG32:$tile"
    cp "$tile" "$OUT_DIR/thumbnails/$(printf '%02d' "$position")-$clue_id.png"
    tiles+=("$tile")
    expected_position=$((expected_position + 1))
done

convert "${tiles[0]}" "${tiles[2]}" "${tiles[1]}" +append "$WORK_DIR/row-1.png"
convert "${tiles[3]}" "${tiles[4]}" "${tiles[5]}" +append "$WORK_DIR/row-2.png"
convert "${tiles[6]}" "${tiles[8]}" "${tiles[7]}" +append "$WORK_DIR/row-3.png"
convert "$WORK_DIR/row-1.png" "$WORK_DIR/row-2.png" "$WORK_DIR/row-3.png" -append \
    -strip \
    -define png:exclude-chunk=date,time \
    -define png:compression-level=9 \
    "PNG32:$OUT_DIR/clue_atlas.png"

#!/bin/bash
set -euo pipefail

cd /app/environment

# --- tools/genabi/layout.cpp: natural alignment + end padding ---
cat > tools/genabi/layout.cpp <<'EOF'
#include "layout.hpp"

static std::size_t align_of(Kind k) {
    switch (k) {
        case Kind::U32:
            return 4;
        case Kind::U64:
        case Kind::PTR:
        case Kind::CSTR:
            return 8;
    }
    return 4;
}

static std::size_t round_up(std::size_t value, std::size_t boundary) {
    if (boundary == 0) {
        return value;
    }
    std::size_t rem = value % boundary;
    return rem == 0 ? value : value + boundary - rem;
}

void compute_layout(LaneModel &model) {
    std::size_t cursor = 0;
    std::size_t widest = 1;
    for (Slot &slot : model.slots) {
        std::size_t place = align_of(slot.kind);
        if (place > widest) {
            widest = place;
        }
        cursor = round_up(cursor, place);
        slot.offset = cursor;
        slot.size = width_of(slot.kind);
        cursor += slot.size;
    }
    model.field_count = model.slots.size();
    model.record_align = widest;
    model.record_size = round_up(cursor, widest);
}
EOF

# --- tools/genabi/digest.cpp: mix pack.order + compat + provenance ---
cat > tools/genabi/digest.cpp <<'EOF'
#include "digest.hpp"

#include <cstdio>
#include <fstream>
#include <sstream>
#include <vector>

namespace {

constexpr std::uint64_t kPrime = 1099511628211ULL;

std::string read_file(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

std::vector<std::string> pack_order(const std::string &idl_dir) {
    std::vector<std::string> order;
    std::ifstream in(idl_dir + "/pack.order");
    std::string line;
    while (std::getline(in, line)) {
        std::string trimmed;
        for (char c : line) {
            if (c != '\r') {
                trimmed.push_back(c);
            }
        }
        std::size_t start = trimmed.find_first_not_of(" \t");
        if (start == std::string::npos) {
            continue;
        }
        std::size_t end = trimmed.find_last_not_of(" \t");
        std::string token = trimmed.substr(start, end - start + 1);
        if (token.empty() || token[0] == '#') {
            continue;
        }
        order.push_back(token);
    }
    return order;
}

}  // namespace

void Mixer::mix_u64(const std::string &text) {
    mix_u64(reinterpret_cast<const unsigned char *>(text.data()), text.size());
}

void Mixer::mix_u64(const unsigned char *data, std::size_t len) {
    for (std::size_t i = 0; i < len; ++i) {
        state_ ^= data[i];
        state_ *= kPrime;
    }
}

std::string Mixer::hex() const {
    char buf[17];
    std::snprintf(buf, sizeof(buf), "%016llx", static_cast<unsigned long long>(state_));
    return std::string(buf);
}

std::string idl_digest(const std::string &idl_dir, const std::string &label) {
    Mixer mixer;
    std::string pack = read_file(idl_dir + "/pack.order");
    mixer.mix_u64(std::string("pack.order"));
    mixer.mix_u64(reinterpret_cast<const unsigned char *>(pack.data()), pack.size());
    for (const std::string &frag : pack_order(idl_dir)) {
        std::string body = read_file(idl_dir + "/fragments/" + frag);
        mixer.mix_u64(frag);
        mixer.mix_u64(reinterpret_cast<const unsigned char *>(body.data()), body.size());
    }
    std::string compat = read_file(idl_dir + "/compat/legacy_slots.tsv");
    mixer.mix_u64(std::string("compat"));
    mixer.mix_u64(reinterpret_cast<const unsigned char *>(compat.data()), compat.size());
    std::string prov = read_file(idl_dir + "/provenance.manifest");
    mixer.mix_u64(std::string("provenance"));
    mixer.mix_u64(reinterpret_cast<const unsigned char *>(prov.data()), prov.size());
    mixer.mix_u64(std::string("lane:") + label);
    return mixer.hex();
}
EOF

# --- build_defs: pack.order participates in generator DEPENDS ---
sed -i 's|set(_idl\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/provenance.manifest"|set(_idl\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/pack.order"\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/provenance.manifest"|' \
  build_defs/SdkToolchain.cmake || true
python3 - <<'PY'
from pathlib import Path
path = Path("build_defs/SdkToolchain.cmake")
text = path.read_text()
needle = '  set(_idl\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/provenance.manifest"'
insert = '  set(_idl\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/pack.order"\n    "${CMAKE_CURRENT_SOURCE_DIR}/idl/provenance.manifest"'
if "idl/pack.order" not in text:
    if needle not in text:
        raise SystemExit("SdkToolchain pack.order anchor missing")
    path.write_text(text.replace(needle, insert, 1))
PY

# --- runbook/idl_fingerprint.sh: include pack.order bytes ---
python3 - <<'PY'
from pathlib import Path
path = Path("runbook/idl_fingerprint.sh")
text = path.read_text()
old = 'pack = idl / "pack.order"\n\norder = ['
new = 'pack = idl / "pack.order"\nmix_text("pack.order")\nmix(pack.read_bytes())\n\norder = ['
if "mix_text(\"pack.order\")" not in text:
    if old not in text:
        raise SystemExit("idl_fingerprint anchor missing")
    path.write_text(text.replace(old, new, 1))
PY

# --- runbook/cache_stamp.sh: stamp on file content ---
cat > runbook/cache_stamp.sh <<'EOF'
#!/usr/bin/env bash

# Profile stamp helpers for warm lane trees.

stamp_key() {
  sha256sum "$1" | awk '{print $1}'
}

stamp_keep() {
  local stamp_file=$1
  local profile_path=$2
  [[ -f "$stamp_file" ]] || return 1
  [[ "$(cat "$stamp_file")" == "$(stamp_key "$profile_path")" ]]
}

stamp_write() {
  local stamp_file=$1
  local profile_path=$2
  stamp_key "$profile_path" > "$stamp_file"
}
EOF

# --- runbook/label_journal.sh: require both digests ---
cat > runbook/label_journal.sh <<'EOF'
#!/usr/bin/env bash

# Per-lane journal helpers. The journal stores fingerprints and counters used
# to decide if a warm lane tree remains current.

lane_journal_path() {
  printf '%s/.sdk-lane.journal\n' "$1"
}

read_configure_epoch() {
  local journal=$1
  local value
  if [[ -f "$journal" ]] && value=$(jq -r '.configure_epoch // 0' "$journal" 2>/dev/null) \
     && [[ -n "$value" && "$value" != "null" ]]; then
    printf '%s\n' "$value"
  else
    printf '0\n'
  fi
}

read_generation_lineage() {
  local journal=$1
  local value
  if [[ -f "$journal" ]] && value=$(jq -r '.generation_lineage // 0' "$journal" 2>/dev/null) \
     && [[ -n "$value" && "$value" != "null" ]]; then
    printf '%s\n' "$value"
  else
    printf '0\n'
  fi
}

# Reports whether the journal describes the current inputs.
journal_fresh() {
  local journal=$1
  local idl_digest=$2
  local tool_digest=$3
  [[ -f "$journal" ]] || return 1
  local stored_idl stored_tool
  stored_idl=$(jq -r '.idl_digest // empty' "$journal" 2>/dev/null) || return 1
  stored_tool=$(jq -r '.tool_digest // empty' "$journal" 2>/dev/null) || return 1
  [[ -n "$stored_idl" && -n "$stored_tool" ]] || return 1
  [[ "$stored_idl" == "$idl_digest" && "$stored_tool" == "$tool_digest" ]]
}

write_lane_journal() {
  local journal=$1
  local lane=$2
  local profile_sha=$3
  local idl_digest=$4
  local tool_digest=$5
  local matrix_sha=$6
  local configure_epoch=$7
  local generation_lineage=$8
  jq -n \
    --arg lane "$lane" \
    --arg profile_sha256 "$profile_sha" \
    --arg idl_digest "$idl_digest" \
    --arg tool_digest "$tool_digest" \
    --arg last_matrix_sha256 "$matrix_sha" \
    --argjson configure_epoch "$configure_epoch" \
    --argjson generation_lineage "$generation_lineage" \
    '{
      schema_version: 1,
      lane: $lane,
      profile_sha256: $profile_sha256,
      idl_digest: $idl_digest,
      tool_digest: $tool_digest,
      last_matrix_sha256: $last_matrix_sha256,
      configure_epoch: $configure_epoch,
      generation_lineage: $generation_lineage
    }' > "$journal"
}

next_configure_epoch() {
  local current
  current=$(read_configure_epoch "$1")
  printf '%s\n' "$((current + 1))"
}

next_generation_lineage() {
  local current
  current=$(read_generation_lineage "$1")
  printf '%s\n' "$((current + 1))"
}
EOF

# --- runbook/release_pass.sh: heal missing lane headers instead of preview fallback ---
python3 - <<'PY'
from pathlib import Path

path = Path("runbook/release_pass.sh")
text = path.read_text()
old = """  header_path=\"$bdir/generated/include/generated/sdk.hpp\"
  layout_src=\"$bdir/generated/sdk.layout.json\"
  # Prefer the checked-in preview when the lane header is absent.
  if [[ ! -f \"$header_path\" ]]; then
    header_path=\"$ENV_ROOT/include/generated/sdk.hpp\"
    layout_src=\"$ENV_ROOT/abi/preview.layout.json\"
  fi

  printf 'build\\t%s\\t%s\\t%s\\n' \"$lane\" \"$bdir\" \"sdk_probe\" >> \"$OUT/trace.tsv\"
"""
new = """  header_path=\"$bdir/generated/include/generated/sdk.hpp\"
  layout_src=\"$bdir/generated/sdk.layout.json\"
  if [[ ! -f \"$header_path\" ]]; then
    printf 'reconcile\\t%s\\t%s\\t%s\\n' \"$lane\" \"$header_path\" \"missing-header\" >> \"$OUT/trace.tsv\"
    cmake --build \"$bdir\" --target sdk_generate >/dev/null
    needs_regenerate=1
  fi

  printf 'build\\t%s\\t%s\\t%s\\n' \"$lane\" \"$bdir\" \"sdk_probe\" >> \"$OUT/trace.tsv\"
"""
if old not in text:
    raise SystemExit("release_pass preview-fallback anchor missing")
path.write_text(text.replace(old, new, 1))
PY

chmod +x runbook/*.sh

bash runbook/release_pass.sh \
  /app/environment/profiles/public.matrix \
  /app/output/sdk-abi-index

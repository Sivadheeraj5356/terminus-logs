#!/usr/bin/env bash
set -euo pipefail

cd /app/environment

cat > bx7/src/step_q2.c <<'EOF'
#include "bx7_api.h"

static int root_path_ok(const char *staged_root) {
    return staged_root && staged_root[0] == '/';
}

static uint32_t seal_for_mode(cap_mode_t mode) {
    if (mode == CAP_STRICT) {
        return 1u;
    }
    return 2u;
}

static void apply_mode(bx7_ctx *ctx, cap_mode_t mode) {
    if (!ctx) {
        return;
    }
    if (mode == CAP_STRICT) {
        ctx->strict_ok = 1;
        ctx->pivot_done = 1;
    } else {
        ctx->strict_ok = 0;
        ctx->pivot_done = 1;
    }
    ctx->gen_seal = seal_for_mode(mode);
}

int render_q2(bx7_ctx *ctx, const char *staged_root, cap_mode_t mode) {
    if (!ctx) {
        return -1;
    }
    if (!root_path_ok(staged_root)) {
        return -2;
    }
    apply_mode(ctx, mode);
    if (ctx->gen_seal == 0) {
        return -3;
    }
    if (mode == CAP_STRICT && (ctx->gen_seal & 1u) == 0u) {
        return -4;
    }
    if (mode == CAP_RELAXED && (ctx->gen_seal & 1u) != 0u) {
        return -5;
    }
    return 0;
}
EOF

cat > lw3/src/phase_m4.c <<'EOF'
#include "lw3_api.h"

#include <stdio.h>
#include <string.h>

static int write_cache_line(
    char *dst,
    size_t dst_sz,
    const char *tree_prefix,
    uint32_t epoch,
    uint32_t gen) {
    return snprintf(
        dst,
        dst_sz,
        "PREFIX=%s\nEPOCH=%u\nGEN=%u\n",
        tree_prefix,
        epoch,
        gen);
}

int emit_m4(lw3_ctx *ctx, const char *tree_prefix, uint32_t epoch, uint32_t gen) {
    int n;
    if (!ctx || !tree_prefix) {
        return -1;
    }
    if (gen == 0) {
        return -3;
    }
    if (strstr(tree_prefix, "HOST") != NULL) {
        return -4;
    }
    n = write_cache_line((char *)ctx->cache, sizeof(ctx->cache), tree_prefix, epoch, gen);
    if (n < 0 || (size_t)n >= sizeof(ctx->cache)) {
        return -2;
    }
    if (strstr((const char *)ctx->cache, "HOSTPREFIX") != NULL) {
        return -5;
    }
    if (strstr((const char *)ctx->cache, "GEN=") == NULL) {
        return -6;
    }
    ctx->cache_len = (size_t)n;
    return 0;
}
EOF

cat > dm5/src/bind_r1.c <<'EOF'
#include "dm5_api.h"

#include <string.h>

static int append_u16(dm5_ctx *ctx, uint16_t value) {
    size_t off = ctx->manifest_len;
    if (off + 2 > sizeof(ctx->manifest)) {
        return -1;
    }
    memcpy(ctx->manifest + off, &value, 2);
    ctx->manifest_len += 2;
    return 0;
}

static int append_u32(dm5_ctx *ctx, uint32_t value) {
    size_t off = ctx->manifest_len;
    if (off + 4 > sizeof(ctx->manifest)) {
        return -1;
    }
    memcpy(ctx->manifest + off, &value, 4);
    ctx->manifest_len += 4;
    return 0;
}

int stamp_r1(dm5_ctx *ctx, const backend_spec *spec, dev_epoch_t epoch, uint32_t gen) {
    size_t i;
    (void)epoch;
    if (!ctx || !spec) {
        return -1;
    }
    if (gen == 0) {
        return -3;
    }
    if (spec->node_count <= 0 || spec->node_count > 8) {
        return -4;
    }
    ctx->manifest_len = 0;
    ctx->manifest[0] = (uint8_t)spec->node_count;
    ctx->manifest_len = 1;
    for (i = 0; i < (size_t)spec->node_count; i++) {
        if (append_u16(ctx, spec->majors[i]) != 0) {
            return -2;
        }
        if (append_u16(ctx, spec->minors[i]) != 0) {
            return -2;
        }
    }
    if (append_u32(ctx, gen) != 0) {
        return -2;
    }
    if (ctx->manifest_len < 5) {
        return -5;
    }
    return 0;
}
EOF

bash scripts/build_all.sh
test -x tools/rk_pack/rk_pack
test -x tools/arena_ctl/arena_ctl

rm -f /app/output/.pack_arena
tools/arena_ctl/arena_ctl --apply-base /app/environment/fx_bins/base/pack_base.bin
tools/rk_pack/rk_pack --matrix --out /tmp/oracle_pack_smoke.json

python3 - <<'PY'
import hashlib
import json
import struct
import sys
from pathlib import Path

app_root = Path("/app/environment")
doc = json.load(open("/tmp/oracle_pack_smoke.json", encoding="utf-8"))
rows = doc.get("rows") or []
if len(rows) != 8:
    sys.exit("expected eight matrix rows")
if not doc.get("manifest_sha256"):
    sys.exit("missing manifest_sha256")

PROFILE_META = {
    "silt": {"tree_prefix": "/stage/silt", "epoch": 1, "backend": "bk_a"},
    "kite": {"tree_prefix": "/stage/kite", "epoch": 2, "backend": "bk_b"},
    "rune": {"tree_prefix": "/stage/rune", "epoch": 3, "backend": "bk_c"},
    "dale": {"tree_prefix": "/stage/dale", "epoch": 4, "backend": "bk_d"},
}

def parse_backend(backend: str):
    spec_path = app_root / "dm5/spec_bins" / f"{backend}.spec"
    count = 0
    pairs = []
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("count="):
            count = int(line.split("=", 1)[1])
        elif line.startswith("dev"):
            _, val = line.split("=", 1)
            maj_s, min_s = val.split(":", 1)
            pairs.append((int(maj_s), int(min_s)))
    return count, pairs[:count]

def gen_for(cap_mode: str) -> int:
    return 1 if cap_mode == "cap_strict" else 2

for row in rows:
    pid = row["public_id"]
    mode = row["cap_mode"]
    gen = gen_for(mode)
    if int(row["gen_seal"]) != gen:
        sys.exit(f"bad gen_seal for {pid}/{mode}")
    meta = PROFILE_META[pid]
    prefix = f"PREFIX={meta['tree_prefix']}\nEPOCH={meta['epoch']}\nGEN={gen}\n".encode()
    count, pairs = parse_backend(meta["backend"])
    manifest = bytearray([count])
    for maj, minor in pairs:
        manifest.extend(struct.pack("<HH", maj, minor))
    manifest.extend(struct.pack("<I", gen))
    if row["prefix_digest"] != hashlib.sha256(prefix).hexdigest():
        sys.exit(f"prefix mismatch {pid}/{mode}")
    if row["dev_digest"] != hashlib.sha256(bytes(manifest)).hexdigest():
        sys.exit(f"dev mismatch {pid}/{mode}")
    replay = hashlib.sha256(prefix + bytes(manifest)).hexdigest()
    if row["replay_digest"] != replay:
        sys.exit(f"replay mismatch {pid}/{mode}")
    if int(row["size_bytes"]) <= 0:
        sys.exit("invalid size_bytes")
PY

rm -f /tmp/oracle_pack_smoke.json /app/output/.pack_arena

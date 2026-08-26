#!/bin/bash
set -euo pipefail

cd /app/environment

# ---------------------------------------------------------------------------
# 1. Read the authoritative documentation before touching any code. The two
#    docs describe the output schema, the digest, the per-window rules, the
#    shared commit log, the boot-era marker, and the exact rebuild commands.
# ---------------------------------------------------------------------------
echo "=== docs/ledger_format.md ==="
sed -n '1,200p' docs/ledger_format.md
echo "=== docs/step_tool.md ==="
sed -n '1,200p' docs/step_tool.md

# ---------------------------------------------------------------------------
# 2. Survey the module tree so the fix sites can be located from behaviour,
#    not guessed. Each window's logic is split across a few small directories.
# ---------------------------------------------------------------------------
echo "=== module tree ==="
ls -R m5s n2h u4r q8k rowpack src | sed -n '1,120p'

# The four entry points named in the docs are the ones worth inspecting.
echo "=== entry points ==="
grep -rn "compute_next_fire\|hour_exists\|decide_sweep\|reconcile_key" \
    --include=*.c --include=*.h . || true

# ---------------------------------------------------------------------------
# 3. Inspect the current (buggy) behaviour of each candidate and the state
#    files the docs mention, to confirm the root cause before editing.
# ---------------------------------------------------------------------------
echo "=== m5s/next_fire.c (backward window: repeated-hour de-dup + slot state) ==="
cat m5s/next_fire.c
echo "=== n2h/hour_exists.c (forward window: absent-hour gate) ==="
cat n2h/hour_exists.c
echo "=== u4r/sweep_decide.c (resume window: catch-up guard) ==="
cat u4r/sweep_decide.c
echo "=== q8k/key_reconcile.c (canonical day-key selection) ==="
cat q8k/key_reconcile.c
echo "=== supporting state referenced by the docs ==="
cat m5s/cadence_policy.conf
cat n2h/missing_hours.tab
sed -n '1,40p' src/commit_log.h src/boot_era.h

# Findings that follow from the docs and the code above:
#  - lane_backward rebinds slot state before every fragment. The stub
#    bind_slot_state resets g_prev_fire without load/save, so the in-memory
#    repeat check never sees the prior fragment and both autumn fragments emit.
#    Fix bind_slot_state to load/save slot_state.rec and collapse the repeat.
#  - hour_exists returns code 1 for an absent hour, which the forward lane reads
#    as "skip". The absent spring hour must instead be reported (code 0) so its
#    single row is still emitted.
#  - decide_sweep looks correct on a fresh rebuild (first pass always emits
#    boot gaps while era is absent) but fails to defer once boot_era.rec already
#    exists, and recovery ignores 0x04 / commit_log. Later catch-up is the trap.
#  - key_reconcile picks the shorter key for a day and ignores the commit log, so
#    an hour-level key loses to the day key across panes.

# ---------------------------------------------------------------------------
# 4. Apply the fixes.
# ---------------------------------------------------------------------------

cat > m5s/next_fire.c <<'EOF'
#include "next_fire.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int64_t g_cadence = CADENCE_SEC;
static int g_repeat_slot = REPEAT_SLOT;
static int g_repeat_guard = 0;
static int64_t g_prev_fire = -1;
static char g_state_path[512];

static void load_policy(void) {
    static int loaded = 0;
    if (loaded) {
        return;
    }
    loaded = 1;
    FILE *fp = fopen("/app/environment/m5s/cadence_policy.conf", "r");
    if (!fp) {
        return;
    }
    char line[128];
    while (fgets(line, sizeof line, fp)) {
        if (strncmp(line, "cadence_sec=", 12) == 0) {
            g_cadence = (int64_t)atoll(line + 12);
        } else if (strncmp(line, "repeat_guard=", 13) == 0) {
            g_repeat_guard = atoi(line + 13);
        } else if (strncmp(line, "repeat_slot_sec=", 16) == 0) {
            g_repeat_slot = atoi(line + 16);
        }
    }
    fclose(fp);
}

static void save_state(void) {
    if (!g_state_path[0]) {
        return;
    }
    FILE *fp = fopen(g_state_path, "w");
    if (!fp) {
        return;
    }
    fprintf(fp, "%lld\n", (long long)g_prev_fire);
    fclose(fp);
}

void bind_slot_state(const char *out_dir) {
    if (!out_dir) {
        return;
    }
    snprintf(g_state_path, sizeof g_state_path, "%s/slot_state.rec", out_dir);
    g_prev_fire = -1;
    FILE *fp = fopen(g_state_path, "r");
    if (fp) {
        if (fscanf(fp, "%lld", (long long *)&g_prev_fire) != 1) {
            g_prev_fire = -1;
        }
        fclose(fp);
    }
}

int compute_next_fire(const char *zone, int64_t anchor, int64_t *next_out) {
    (void)zone;
    if (!next_out) {
        return -1;
    }
    load_policy();
    if (!g_repeat_guard) {
        *next_out = anchor + g_cadence;
        return 0;
    }
    if (g_prev_fire >= 0 && (anchor - g_prev_fire) == g_repeat_slot) {
        g_prev_fire = anchor;
        save_state();
        *next_out = anchor + g_cadence;
        return 2;
    }
    g_prev_fire = anchor;
    int64_t day_base = anchor - (anchor % g_cadence);
    int64_t slot = anchor - day_base;
    if (slot >= g_repeat_slot && slot < (g_repeat_slot * 2)) {
        *next_out = day_base + g_cadence;
        save_state();
        return 0;
    }
    *next_out = anchor + g_cadence;
    save_state();
    return 0;
}
EOF

cat > n2h/hour_exists.c <<'EOF'
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static int lookup_hour(int hour_slot) {
    FILE *fp = fopen("/app/environment/n2h/missing_hours.tab", "r");
    if (!fp) {
        return 1;
    }
    char line[128];
    while (fgets(line, sizeof line, fp)) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        int hh = -1;
        int exists = 1;
        if (sscanf(line, "%d %d", &hh, &exists) == 2 && hh == hour_slot) {
            fclose(fp);
            return exists;
        }
    }
    fclose(fp);
    return 1;
}

int hour_exists(const char *zone, int hour_slot, int *exists_out) {
    (void)zone;
    if (!exists_out) {
        return -1;
    }
    *exists_out = lookup_hour(hour_slot);
    return 0;
}
EOF

cat > u4r/sweep_decide.c <<'EOF'
#include "../src/commit_log.h"
#include "../src/boot_era.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TZ_SKIP_FLAG 0x04

static int read_frag_fields(const char *frag_path, char *key, size_t key_cap, int *flags_out) {
    (void)key_cap;
    FILE *fp = fopen(frag_path, "r");
    if (!fp) {
        return -1;
    }
    char line[256];
    if (!fgets(line, sizeof line, fp)) {
        fclose(fp);
        return -2;
    }
    fclose(fp);
    int wall = 0;
    int seq = 0;
    int flags = 0;
    if (sscanf(line, "%31[^|]|%d|%d|%i", key, &wall, &seq, &flags) < 1) {
        return -3;
    }
    if (flags_out) {
        *flags_out = flags;
    }
    (void)wall;
    (void)seq;
    return 0;
}

int decide_sweep(const char *frag_path, int boot_gap, int recovery_mode, int *exec_out) {
    if (!exec_out) {
        return -1;
    }
    if (!boot_gap) {
        *exec_out = 0;
        return 0;
    }
    if (!recovery_mode) {
        /* Initial rebuild: emit boot-gap fragments on the first pass while the
         * era marker is still absent. Once era already exists from a prior
         * resume step, leave uncommitted boot gaps for the recovery pass. */
        if (boot_era_read(BOOT_ERA_PATH) >= 1) {
            *exec_out = 0;
            return 0;
        }
        *exec_out = 1;
        return 0;
    }
    if (boot_era_read(BOOT_ERA_PATH) < 1) {
        *exec_out = 0;
        return 0;
    }
    char key[32];
    int flags = 0;
    if (read_frag_fields(frag_path, key, sizeof key, &flags) != 0) {
        *exec_out = 0;
        return 0;
    }
    if (flags & TZ_SKIP_FLAG) {
        *exec_out = 0;
        return 0;
    }
    if (commit_log_has_key(COMMIT_LOG_PATH, key)) {
        *exec_out = 0;
        return 0;
    }
    *exec_out = 1;
    return 0;
}
EOF

cat > q8k/key_reconcile.c <<'EOF'
#include "../src/commit_log.h"

#include <stdio.h>
#include <string.h>

static int finest_from_commit(const char *day8, char *out, size_t cap) {
    FILE *fp = fopen(COMMIT_LOG_PATH, "r");
    if (!fp) {
        return -1;
    }
    char best[32] = "";
    char line[256];
    while (fgets(line, sizeof line, fp)) {
        char win[32];
        char k[32];
        int seq = 0;
        int fl = 0;
        if (sscanf(line, "%31s %31s %d %d", win, k, &seq, &fl) < 2) {
            continue;
        }
        if (strncmp(k, day8, 8) != 0) {
            continue;
        }
        if (!best[0] || strlen(k) > strlen(best)) {
            strncpy(best, k, sizeof best - 1);
            best[sizeof best - 1] = '\0';
        }
    }
    fclose(fp);
    if (!best[0]) {
        return -2;
    }
    strncpy(out, best, cap - 1);
    out[cap - 1] = '\0';
    return 0;
}

int reconcile_key(const char *rows_path, char *key_out, size_t cap) {
    if (!rows_path || !key_out || cap == 0) {
        return -1;
    }
    FILE *fp = fopen(rows_path, "r");
    if (!fp) {
        return -2;
    }
    char keys[32][32];
    int nkeys = 0;
    char line[256];
    while (fgets(line, sizeof line, fp) && nkeys < 32) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        if (sscanf(line, "%31[^|]", keys[nkeys]) == 1) {
            nkeys++;
        }
    }
    fclose(fp);
    if (nkeys <= 0) {
        return -3;
    }
    char day8[9];
    strncpy(day8, keys[nkeys - 1], 8);
    day8[8] = '\0';

    char canon[32] = "";
    for (int i = 0; i < nkeys; i++) {
        if (strncmp(keys[i], day8, 8) != 0) {
            continue;
        }
        if (!canon[0] || strlen(keys[i]) > strlen(canon)) {
            strncpy(canon, keys[i], sizeof canon - 1);
            canon[sizeof canon - 1] = '\0';
        }
    }
    if (!canon[0]) {
        strncpy(canon, keys[nkeys - 1], sizeof canon - 1);
        canon[sizeof canon - 1] = '\0';
    }
    char finest[32];
    if (finest_from_commit(day8, finest, sizeof finest) == 0) {
        if (strlen(finest) > strlen(canon)) {
            strncpy(canon, finest, sizeof canon - 1);
            canon[sizeof canon - 1] = '\0';
        }
    } else if (commit_log_finest_for_day(COMMIT_LOG_PATH, day8, finest, sizeof finest) == 0) {
        if (strlen(finest) > strlen(canon)) {
            strncpy(canon, finest, sizeof canon - 1);
            canon[sizeof canon - 1] = '\0';
        }
    }
    strncpy(key_out, canon, cap - 1);
    key_out[cap - 1] = '\0';
    return 0;
}
EOF

# ---------------------------------------------------------------------------
# 5. Rebuild the tools and replay the documented command sequence from scratch.
# ---------------------------------------------------------------------------
make clean all
mkdir -p /app/tools /app/output/step
cp build/step_tool /app/tools/step_tool
cp build/pack_tool /app/tools/pack_tool

/app/tools/step_tool --pane backward --env /app/data/windows/backward/window.conf --trace /app/data/traces/backward.rows --out /app/output/step/backward
/app/tools/step_tool --pane forward  --env /app/data/windows/forward/window.conf  --trace /app/data/traces/forward.rows  --out /app/output/step/forward
/app/tools/step_tool --pane resume   --env /app/data/windows/resume/window.conf   --trace /app/data/traces/resume.rows   --out /app/output/step/resume
/app/tools/pack_tool --step-root /app/output/step --out /app/output/schedule_ledger.json

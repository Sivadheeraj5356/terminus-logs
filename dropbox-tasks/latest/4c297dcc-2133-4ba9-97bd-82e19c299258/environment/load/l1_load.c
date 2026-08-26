#include "hop_cfg.h"
#include "role_snap.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void snap_clear(RoleSnap *rs)
{
    memset(rs, 0, sizeof *rs);
}

static int decode_escapes(const char *in, RoleSnap *out, uint8_t wire_tag)
{
    size_t oi = 0;
    const unsigned char *p;
    BufKind kind = BK_A5;

    snap_clear(out);
    if (!in) {
        return -1;
    }
    if (wire_tag == 0x0c) {
        kind = BK_U8;
    } else if (wire_tag == 0x16) {
        kind = BK_A5;
    }
    out->wire_tag = wire_tag;
    out->kind = kind;
    for (p = (const unsigned char *)in; *p && oi + 1 < RB_MAX; p++) {
        if (p[0] == '\\' && p[1] == 'x' && p[2] && p[3]) {
            unsigned v = 0;
            if (sscanf((const char *)p + 2, "%2x", &v) == 1) {
                out->bytes[oi++] = (unsigned char)v;
                p += 3;
                continue;
            }
        }
        out->bytes[oi++] = *p;
    }
    out->len = oi;
    for (size_t i = 0; i < oi && i + 1 < RB_MAX; i++) {
        out->display[i] = (char)out->bytes[i];
    }
    out->display[oi < RB_MAX ? oi : RB_MAX - 1] = '\0';
    return 0;
}

static int read_line(FILE *fp, char *buf, size_t cap)
{
    if (!fgets(buf, (int)cap, fp)) {
        return -1;
    }
    buf[strcspn(buf, "\n\r")] = '\0';
    return 0;
}

static int load_tgt_row(const char *fixture_dir, char *line, size_t cap, uint32_t *row_bits,
                        uint32_t *cap_max)
{
    char path[512];
    FILE *fp;
    char buf[HC_LINE];

    snprintf(path, sizeof path, "%s/tgt.te", fixture_dir);
    fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    line[0] = '\0';
    if (row_bits) {
        *row_bits = 0;
    }
    if (cap_max) {
        *cap_max = 0xFFFFFFFFu;
    }
    while (read_line(fp, buf, sizeof buf) == 0) {
        if (strncmp(buf, "ROW:", 4) == 0) {
            snprintf(line, cap, "%s", buf + 4);
        }
        if (row_bits && strncmp(buf, "ROWBITS:", 8) == 0) {
            *row_bits = (uint32_t)strtoul(buf + 8, NULL, 0);
        }
        if (cap_max && strncmp(buf, "CAPMAX:", 7) == 0) {
            *cap_max = (uint32_t)strtoul(buf + 7, NULL, 0);
        }
    }
    fclose(fp);
    return line[0] ? 0 : -1;
}

int hops_load(const char *fixture_dir, HopSet *out)
{
    char path[512];
    FILE *fp;
    HostCfg scratch;
    char line[HC_LINE];
    char tgt_row[HC_LINE];
    uint32_t row_bits = 0;
    uint32_t cap_max = 0xFFFFFFFFu;
    uint8_t role_tag = 0x16;
    uint8_t alt_tag = 0x16;

    if (!fixture_dir || !out) {
        return -1;
    }
    memset(out, 0, sizeof *out);
    if (load_tgt_row(fixture_dir, tgt_row, sizeof tgt_row, &row_bits, &cap_max) != 0) {
        return -1;
    }
    snprintf(path, sizeof path, "%s/src.te", fixture_dir);
    fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    memset(&scratch, 0, sizeof scratch);
    snprintf(scratch.line_text, sizeof scratch.line_text, "%s", tgt_row);
    scratch.row_bits = row_bits;
    scratch.cap_ceil = cap_max;
    while (read_line(fp, line, sizeof line) == 0) {
        if (line[0] == '#' || line[0] == '\0') {
            continue;
        }
        if (strncmp(line, "PAIR:", 5) == 0) {
            if (scratch.pair_label[0] && scratch.src.len > 0 && out->count < DCASE_MAX) {
                out->items[out->count++] = scratch;
            }
            memset(&scratch, 0, sizeof scratch);
            snprintf(scratch.line_text, sizeof scratch.line_text, "%s", tgt_row);
            scratch.row_bits = row_bits;
            scratch.cap_ceil = cap_max;
            snprintf(scratch.pair_label, sizeof scratch.pair_label, "%s", line + 5);
            snap_clear(&scratch.src);
            snap_clear(&scratch.alt);
            role_tag = 0x16;
            alt_tag = 0x16;
            continue;
        }
        if (strncmp(line, "TAG:", 4) == 0) {
            unsigned v = 0;
            if (sscanf(line + 4, "%x", &v) == 1) {
                role_tag = (uint8_t)v;
            }
            continue;
        }
        if (strncmp(line, "STAG:", 5) == 0) {
            unsigned v = 0;
            if (sscanf(line + 5, "%x", &v) == 1) {
                alt_tag = (uint8_t)v;
            }
            continue;
        }
        if (strncmp(line, "CAP:", 4) == 0) {
            scratch.src.cap_bits = (uint32_t)strtoul(line + 4, NULL, 0);
            continue;
        }
        if (strncmp(line, "LANE:", 5) == 0) {
            scratch.lane_fd = atoi(line + 5);
            continue;
        }
        if (strncmp(line, "ROLE:", 5) == 0) {
            uint32_t keep = scratch.src.cap_bits;
            decode_escapes(line + 5, &scratch.src, role_tag);
            scratch.src.cap_bits = keep;
            continue;
        }
        if (strncmp(line, "ALT:", 4) == 0) {
            decode_escapes(line + 4, &scratch.alt, alt_tag);
            continue;
        }
    }
    if (scratch.pair_label[0] && scratch.src.len > 0 && out->count < DCASE_MAX) {
        out->items[out->count++] = scratch;
    }
    fclose(fp);
    return out->count > 0 ? 0 : -1;
}

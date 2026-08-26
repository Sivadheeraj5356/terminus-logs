#include "engine.h"
#include "scenario_device.h"
#include "scenario_linker.h"
#include "scenario_root.h"

#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define ENV_ROOT "/app/environment"
#define ARENA_PATH "/app/output/.pack_arena"
#define MAX_ROWS 16
#define ARENA_MAGIC 0x43534B50u /* PKSC */
#define RESET_MARKER 0x44454553u /* SEED */

typedef struct {
    char public_id[16];
    char tree_prefix[64];
    char backend[16];
    uint32_t epoch;
    uint32_t seed;
    int size_ceiling;
} profile_row;

typedef struct {
    char public_id[16];
    char cap_mode[16];
    char prefix_digest[65];
    char dev_digest[65];
    char replay_digest[65];
    int size_bytes;
    uint32_t gen_seal;
} trace_row;

typedef struct {
    uint32_t magic;
    uint32_t generation;
    uint32_t dirty;
    uint32_t marker;
} arena_hdr;

static void trim_inplace(char *token) {
    char *start = token;
    char *end;
    if (!token) {
        return;
    }
    while (*start == ' ' || *start == '\t') {
        start++;
    }
    if (start != token) {
        memmove(token, start, strlen(start) + 1);
    }
    end = token + strlen(token);
    while (end > token && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\n' || end[-1] == '\r')) {
        end--;
    }
    *end = '\0';
}

static int parse_profile(const char *path, profile_row *row) {
    FILE *fp = fopen(path, "r");
    char line[256];
    if (!fp) {
        return -1;
    }
    memset(row, 0, sizeof(*row));
    while (fgets(line, sizeof(line), fp)) {
        char key[64];
        char val[128];
        char *cursor = line;
        while (*cursor == ' ' || *cursor == '\t') {
            cursor++;
        }
        if (sscanf(cursor, "%63[^=] = \"%127[^\"]\"", key, val) == 2) {
            trim_inplace(key);
            if (strcmp(key, "public_id") == 0) {
                strncpy(row->public_id, val, sizeof(row->public_id) - 1);
            } else if (strcmp(key, "tree_prefix") == 0) {
                strncpy(row->tree_prefix, val, sizeof(row->tree_prefix) - 1);
            } else if (strcmp(key, "backend") == 0) {
                strncpy(row->backend, val, sizeof(row->backend) - 1);
            }
        } else if (sscanf(cursor, "%63[^=] = %127s", key, val) == 2) {
            trim_inplace(key);
            if (strcmp(key, "epoch") == 0) {
                row->epoch = (uint32_t)strtoul(val, NULL, 10);
            } else if (strcmp(key, "seed") == 0) {
                row->seed = (uint32_t)strtoul(val, NULL, 10);
            } else if (strcmp(key, "size_ceiling") == 0) {
                row->size_ceiling = atoi(val);
            }
        }
    }
    fclose(fp);
    return row->public_id[0] ? 0 : -1;
}

static int parse_backend(const char *backend, backend_spec *spec) {
    char path[512];
    FILE *fp;
    char line[128];
    snprintf(path, sizeof(path), ENV_ROOT "/dm5/spec_bins/%s.spec", backend);
    fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    memset(spec, 0, sizeof(*spec));
    while (fgets(line, sizeof(line), fp)) {
        char key[32];
        char val[64];
        if (sscanf(line, "%31[^=]=%63s", key, val) != 2) {
            continue;
        }
        if (strcmp(key, "name") == 0) {
            strncpy(spec->name, val, sizeof(spec->name) - 1);
        } else if (strcmp(key, "count") == 0) {
            spec->node_count = atoi(val);
        } else if (strncmp(key, "dev", 3) == 0) {
            int idx = atoi(key + 3);
            unsigned int maj = 0;
            unsigned int min = 0;
            if (idx >= 0 && idx < 8 && sscanf(val, "%u:%u", &maj, &min) == 2) {
                spec->majors[idx] = (uint16_t)maj;
                spec->minors[idx] = (uint16_t)min;
            }
        }
    }
    fclose(fp);
    return spec->node_count > 0 ? 0 : -1;
}

static void sha256_hex(const uint8_t *data, size_t len, char out_hex[65]) {
    unsigned char digest[32];
    unsigned int digest_len = 0;
    memset(out_hex, 0, 65);
    EVP_Digest(data, len, digest, &digest_len, EVP_sha256(), NULL);
    for (int i = 0; i < 32; i++) {
        snprintf(out_hex + (i * 2), 3, "%02x", digest[i]);
    }
}

static void sha256_concat_hex(
    const uint8_t *a,
    size_t a_len,
    const uint8_t *b,
    size_t b_len,
    char out_hex[65]) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    unsigned char digest[32];
    unsigned int digest_len = 0;
    memset(out_hex, 0, 65);
    if (!ctx) {
        return;
    }
    EVP_DigestInit_ex(ctx, EVP_sha256(), NULL);
    EVP_DigestUpdate(ctx, a, a_len);
    EVP_DigestUpdate(ctx, b, b_len);
    EVP_DigestFinal_ex(ctx, digest, &digest_len);
    EVP_MD_CTX_free(ctx);
    for (int i = 0; i < 32; i++) {
        snprintf(out_hex + (i * 2), 3, "%02x", digest[i]);
    }
}

static int arena_load(arena_hdr *hdr) {
    FILE *fp = fopen(ARENA_PATH, "rb");
    memset(hdr, 0, sizeof(*hdr));
    if (!fp) {
        return 0;
    }
    if (fread(hdr, sizeof(*hdr), 1, fp) != 1) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 1;
}

static int arena_store(const arena_hdr *hdr) {
    FILE *fp;
    mkdir("/app/output", 0755);
    fp = fopen(ARENA_PATH, "wb");
    if (!fp) {
        return -1;
    }
    if (fwrite(hdr, sizeof(*hdr), 1, fp) != 1) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}

static int arena_preflight(void) {
    arena_hdr hdr;
    int loaded = arena_load(&hdr);
    if (loaded < 0) {
        return -10; /* truncated / corrupt */
    }
    if (loaded == 0) {
        return 0; /* absent is clean */
    }
    if (hdr.magic != ARENA_MAGIC) {
        return -11; /* corrupt magic */
    }
    if (hdr.dirty != 0) {
        return -12; /* dirty without recovery */
    }
    return 0;
}

static int arena_mark_dirty(uint32_t generation) {
    arena_hdr hdr;
    hdr.magic = ARENA_MAGIC;
    hdr.generation = generation;
    hdr.dirty = 1;
    hdr.marker = 0;
    return arena_store(&hdr);
}

static int cache_has_host_marker(const lw3_ctx *ctx) {
    return ctx && ctx->cache_len > 0 && strstr((const char *)ctx->cache, "HOSTPREFIX") != NULL;
}

static int gen_parity_ok(cap_mode_t mode, uint32_t gen) {
    if (gen == 0) {
        return 0;
    }
    if (mode == CAP_STRICT) {
        return (gen & 1u) == 1u;
    }
    return (gen & 1u) == 0u;
}

static int run_pack_row(
    const profile_row *prof,
    cap_mode_t cap_mode,
    trace_row *out_row) {
    bx7_ctx bx7;
    lw3_ctx lw3;
    dm5_ctx dm5;
    backend_spec spec;
    const char *cap_label = (cap_mode == CAP_STRICT) ? "cap_strict" : "cap_relaxed";

    memset(&bx7, 0, sizeof(bx7));
    memset(&lw3, 0, sizeof(lw3));
    memset(&dm5, 0, sizeof(dm5));

    if (parse_backend(prof->backend, &spec) != 0) {
        return -1;
    }
    if (scenario_root_rebind(&bx7, "/app/output/stage", cap_mode) != 0) {
        return -2;
    }
    if (cap_mode == CAP_STRICT && !bx7.strict_ok) {
        return -5;
    }
    if (!gen_parity_ok(cap_mode, bx7.gen_seal)) {
        return -8;
    }
    if (scenario_linker_cache(&lw3, prof->tree_prefix, prof->epoch, bx7.gen_seal) != 0) {
        return -3;
    }
    if (scenario_device_manifest(&dm5, &spec, prof->epoch, bx7.gen_seal) != 0) {
        return -4;
    }

    strncpy(out_row->public_id, prof->public_id, sizeof(out_row->public_id) - 1);
    strncpy(out_row->cap_mode, cap_label, sizeof(out_row->cap_mode) - 1);
    sha256_hex(lw3.cache, lw3.cache_len, out_row->prefix_digest);
    sha256_hex(dm5.manifest, dm5.manifest_len, out_row->dev_digest);
    sha256_concat_hex(lw3.cache, lw3.cache_len, dm5.manifest, dm5.manifest_len, out_row->replay_digest);
    out_row->size_bytes = (int)(lw3.cache_len + dm5.manifest_len + 64);
    out_row->gen_seal = bx7.gen_seal;

    if (cache_has_host_marker(&lw3)) {
        return -6;
    }
    if (out_row->size_bytes > prof->size_ceiling) {
        return -7;
    }
    return 0;
}

static void manifest_over_rows(const trace_row *rows, size_t count, char out_hex[65]) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    unsigned char digest[32];
    unsigned int digest_len = 0;
    memset(out_hex, 0, 65);
    if (!ctx) {
        return;
    }
    EVP_DigestInit_ex(ctx, EVP_sha256(), NULL);
    for (size_t i = 0; i < count; i++) {
        EVP_DigestUpdate(ctx, rows[i].prefix_digest, strlen(rows[i].prefix_digest));
        EVP_DigestUpdate(ctx, rows[i].dev_digest, strlen(rows[i].dev_digest));
        EVP_DigestUpdate(ctx, rows[i].replay_digest, strlen(rows[i].replay_digest));
    }
    EVP_DigestFinal_ex(ctx, digest, &digest_len);
    EVP_MD_CTX_free(ctx);
    for (int i = 0; i < 32; i++) {
        snprintf(out_hex + (i * 2), 3, "%02x", digest[i]);
    }
}

static int write_trace(const char *out_path, const char *manifest_sha256, trace_row *rows, size_t count) {
    FILE *fp = fopen(out_path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n  \"manifest_sha256\": \"%s\",\n  \"rows\": [\n", manifest_sha256);
    for (size_t i = 0; i < count; i++) {
        fprintf(
            fp,
            "    {\"public_id\":\"%s\",\"cap_mode\":\"%s\",\"prefix_digest\":\"%s\","
            "\"dev_digest\":\"%s\",\"replay_digest\":\"%s\",\"size_bytes\":%d,"
            "\"gen_seal\":%u}%s\n",
            rows[i].public_id,
            rows[i].cap_mode,
            rows[i].prefix_digest,
            rows[i].dev_digest,
            rows[i].replay_digest,
            rows[i].size_bytes,
            rows[i].gen_seal,
            (i + 1 < count) ? "," : "");
    }
    fprintf(fp, "  ]\n}\n");
    fclose(fp);
    return 0;
}

int rk_run_matrix(const char *out_path) {
    char out_dir[512];
    char *slash;
    const char *profiles[] = {
        ENV_ROOT "/prf_defs/prf_s1.toml",
        ENV_ROOT "/prf_defs/prf_s2.toml",
        ENV_ROOT "/prf_defs/prf_s3.toml",
        ENV_ROOT "/prf_defs/prf_s4.toml",
    };
    trace_row rows[MAX_ROWS];
    char manifest_sha256[65];
    size_t row_count = 0;
    uint32_t max_gen = 0;
    int pre;

    pre = arena_preflight();
    if (pre != 0) {
        return 4;
    }

    strncpy(out_dir, out_path, sizeof(out_dir) - 1);
    out_dir[sizeof(out_dir) - 1] = '\0';
    slash = strrchr(out_dir, '/');
    if (slash) {
        *slash = '\0';
        mkdir(out_dir, 0755);
    }

    for (size_t i = 0; i < sizeof(profiles) / sizeof(profiles[0]); i++) {
        profile_row prof;
        cap_mode_t modes[] = {CAP_STRICT, CAP_RELAXED};
        if (parse_profile(profiles[i], &prof) != 0) {
            return 1;
        }
        for (size_t m = 0; m < 2; m++) {
            if (run_pack_row(&prof, modes[m], &rows[row_count]) != 0) {
                return 2;
            }
            if (rows[row_count].gen_seal > max_gen) {
                max_gen = rows[row_count].gen_seal;
            }
            row_count++;
        }
    }

    manifest_over_rows(rows, row_count, manifest_sha256);
    if (write_trace(out_path, manifest_sha256, rows, row_count) != 0) {
        return 3;
    }
    if (arena_mark_dirty(max_gen) != 0) {
        return 5;
    }
    return 0;
}

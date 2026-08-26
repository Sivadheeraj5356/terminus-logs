#include "tel_report.h"

#include "tel_crc32c.h"
#include "tel_sha256.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int write_pid_array(FILE *fp, const uint64_t *pids, size_t len) {
    fputc('[', fp);
    for (size_t i = 0; i < len; i++) {
        if (i) {
            fputc(',', fp);
        }
        fprintf(fp, "%llu", (unsigned long long)pids[i]);
    }
    fputc(']', fp);
    return 0;
}

static int fill_body_sha256(tel_scenario_report_t *s) {
    char *buf = NULL;
    size_t cap = 0;
    FILE *mem = open_memstream(&buf, &cap);
    if (!mem) {
        return -1;
    }
    fprintf(mem,
            "{\"affected_pids\":");
    write_pid_array(mem, s->affected_pids, s->affected_pids_len);
    fprintf(mem,
            ",\"correlated_triples\":%d,\"errors_seen\":%d,\"fd_delta\":%d,"
            "\"final_open_fds\":%d,\"initial_open_fds\":%d,\"leak_reproduced\":%s,"
            "\"loops_run\":%d,\"restarts_seen\":%d,\"root_cause\":\"%s\","
            "\"samples_scanned\":%d,\"scenario_id\":\"%s\",\"schema_version\":%d}",
            s->correlated_triples, s->errors_seen, s->fd_delta, s->final_open_fds,
            s->initial_open_fds, s->leak_reproduced ? "true" : "false", s->loops_run,
            s->restarts_seen, s->root_cause, s->samples_scanned, s->scenario_id,
            s->schema_version);
    fclose(mem);
    tel_sha256_hex(buf, strlen(buf), s->body_sha256);
    free(buf);
    return 0;
}

static void write_seal(const tel_matrix_report_t *rep, const char *seal_path) {
    unsigned char digest_raw[32];
    tel_sha256_raw(rep->matrix_digest, strlen(rep->matrix_digest), digest_raw);

    int64_t fd_sum = 0;
    for (size_t i = 0; i < rep->scenario_count; i++) {
        fd_sum += rep->scenarios[i].fd_delta;
    }

    unsigned char seal[40];
    memcpy(seal, digest_raw, 16);
    memcpy(seal + 16, &fd_sum, 8);
    uint64_t count_be = rep->scenario_count;
    for (int i = 0; i < 8; i++) {
        seal[24 + i] = (unsigned char)((count_be >> (56 - 8 * i)) & 0xff);
    }
    uint32_t crc = tel_crc32c(seal, 32);
    memcpy(seal + 32, &crc, 4);
    memset(seal + 36, 0, 4);

    FILE *fp = fopen(seal_path, "wb");
    if (fp) {
        fwrite(seal, 1, 40, fp);
        fclose(fp);
    }
}

int tel_report_write_matrix(tel_matrix_report_t *rep, const char *json_path,
                            const char *seal_path) {
    for (size_t i = 0; i < rep->scenario_count; i++) {
        if (fill_body_sha256(&rep->scenarios[i]) != 0) {
            return -1;
        }
    }

    char digest_input[4096] = {0};
    size_t off = 0;
    for (size_t i = 0; i < rep->scenario_count; i++) {
        size_t n = strlen(rep->scenarios[i].body_sha256);
        if (off + n >= sizeof(digest_input)) {
            return -1;
        }
        memcpy(digest_input + off, rep->scenarios[i].body_sha256, n);
        off += n;
    }
    tel_sha256_hex(digest_input, off, rep->matrix_digest);

    FILE *fp = fopen(json_path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\"matrix_digest\":\"%s\",\"schema_version\":%d,\"scenarios\":{",
            rep->matrix_digest, rep->schema_version);
    for (size_t i = 0; i < rep->scenario_count; i++) {
        const tel_scenario_report_t *s = &rep->scenarios[i];
        if (i) {
            fputc(',', fp);
        }
        fprintf(fp, "\"%s\":{", s->scenario_id);
        fprintf(fp, "\"affected_pids\":");
        write_pid_array(fp, s->affected_pids, s->affected_pids_len);
        fprintf(fp,
                ",\"body_sha256\":\"%s\",\"correlated_triples\":%d,\"errors_seen\":%d,"
                "\"fd_delta\":%d,\"final_open_fds\":%d,\"initial_open_fds\":%d,"
                "\"leak_reproduced\":%s,\"loops_run\":%d,\"restarts_seen\":%d,"
                "\"root_cause\":\"%s\",\"samples_scanned\":%d,\"scenario_id\":\"%s\","
                "\"schema_version\":%d}",
                s->body_sha256, s->correlated_triples, s->errors_seen, s->fd_delta,
                s->final_open_fds, s->initial_open_fds, s->leak_reproduced ? "true" : "false",
                s->loops_run, s->restarts_seen, s->root_cause, s->samples_scanned,
                s->scenario_id, s->schema_version);
    }
    fprintf(fp, "}}");
    fclose(fp);

    write_seal(rep, seal_path);
    return 0;
}

void tel_report_free_matrix(tel_matrix_report_t *rep) {
    if (!rep) {
        return;
    }
    for (size_t i = 0; i < rep->scenario_count; i++) {
        free(rep->scenarios[i].affected_pids);
    }
    free(rep->scenarios);
    rep->scenarios = NULL;
    rep->scenario_count = 0;
}

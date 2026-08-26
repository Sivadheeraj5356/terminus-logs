#include "report.h"

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <jansson.h>
#include <openssl/sha.h>

static int sha256_file(const char *path, char *hex_out, size_t hex_cap) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return -1;
    }
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    unsigned char buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) {
        SHA256_Update(&ctx, buf, n);
    }
    if (ferror(f)) {
        fclose(f);
        return -1;
    }
    fclose(f);
    unsigned char dig[SHA256_DIGEST_LENGTH];
    SHA256_Final(dig, &ctx);
    if (hex_cap < 65) {
        return -1;
    }
    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        sprintf(hex_out + 2 * i, "%02x", dig[i]);
    }
    hex_out[64] = '\0';
    return 0;
}

static int sha256_bytes(const unsigned char *data, size_t n, char *hex_out,
                        size_t hex_cap) {
    unsigned char dig[SHA256_DIGEST_LENGTH];
    SHA256(data, n, dig);
    if (hex_cap < 65) {
        return -1;
    }
    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        sprintf(hex_out + 2 * i, "%02x", dig[i]);
    }
    hex_out[64] = '\0';
    return 0;
}

int schema_bind(const char *schema_path, char *digest_out, size_t digest_cap) {
    if (sha256_file(schema_path, digest_out, digest_cap) != 0) {
        return -1;
    }
    json_error_t err;
    json_t *doc = json_load_file(schema_path, 0, &err);
    if (!doc) {
        return -1;
    }
    json_t *marker = json_object_get(doc, "x-tofmass-report-version");
    int ok = json_is_integer(marker) && json_integer_value(marker) == 2;
    json_decref(doc);
    return ok ? 0 : -1;
}

static void append_fmt(char **buf, size_t *len, size_t *cap, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    char tmp[1024];
    int n = vsnprintf(tmp, sizeof(tmp), fmt, ap);
    va_end(ap);
    if (n < 0) {
        return;
    }
    if (*len + (size_t)n + 1 > *cap) {
        size_t ncap = (*cap ? *cap * 2 : 4096);
        while (ncap < *len + (size_t)n + 1) {
            ncap *= 2;
        }
        char *nb = realloc(*buf, ncap);
        if (!nb) {
            return;
        }
        *buf = nb;
        *cap = ncap;
    }
    memcpy(*buf + *len, tmp, (size_t)n);
    *len += (size_t)n;
    (*buf)[*len] = '\0';
}

static char *build_ledger(const char *schema_digest, const ReconcileResult *result) {
    char *buf = NULL;
    size_t len = 0, cap = 0;
    append_fmt(&buf, &len, &cap, "schema|version=2|sha256=%s", schema_digest);
    append_fmt(&buf, &len, &cap,
               "\naxis|k=%.12e|t0=%.12e|q=%.12e|c00=%.12e|c01=%.12e|c02=%.12e|"
               "c11=%.12e|c12=%.12e|c22=%.12e|source=%s",
               result->theta.v[0], result->theta.v[1], result->theta.v[2],
               result->cov.m[0][0], result->cov.m[0][1], result->cov.m[0][2],
               result->cov.m[1][1], result->cov.m[1][2], result->cov.m[2][2],
               result->source);
    for (size_t i = 0; i < result->used_count; i++) {
        append_fmt(&buf, &len, &cap, "\nused|%s", result->used_keys[i]);
    }
    for (size_t i = 0; i < result->rejected.count; i++) {
        append_fmt(&buf, &len, &cap, "\nrejected|%s|%s",
                   result->rejected.items[i].candidate_key,
                   result->rejected.items[i].reason);
    }
    for (size_t i = 0; i < result->peak_count; i++) {
        const PeakResult *p = &result->peaks[i];
        if (p->has_catalog) {
            append_fmt(&buf, &len, &cap,
                       "\npeak|%s|tof=%.10f|sigma_tof=%.12e|mass=%.10f|sigma=%.12e|"
                       "catalog=%s|residual=%.10f|z=%.10f|accepted=%d|reason=%s",
                       p->peak_id, p->tof_us, p->tof_sigma_us, p->corrected_da,
                       p->sigma_corr_da, p->catalog_id, p->residual_da, p->z_score,
                       p->accepted ? 1 : 0,
                       p->accepted ? "-" : p->reject_reason);
        } else {
            append_fmt(&buf, &len, &cap,
                       "\npeak|%s|tof=%.10f|sigma_tof=%.12e|mass=%.10f|sigma=%.12e|"
                       "catalog=-|residual=null|z=null|accepted=0|reason=%s",
                       p->peak_id, p->tof_us, p->tof_sigma_us, p->corrected_da,
                       p->sigma_corr_da, p->reject_reason);
        }
    }
    return buf;
}

static int atomic_write(const char *out_path, const char *data, size_t n) {
    char dir[1024];
    snprintf(dir, sizeof(dir), "%s", out_path);
    char *slash = strrchr(dir, '/');
    if (slash) {
        *slash = '\0';
    } else {
        snprintf(dir, sizeof(dir), ".");
    }

    char tmp[1100];
    snprintf(tmp, sizeof(tmp), "%s/.tofmass-report-XXXXXX", dir);
    int fd = mkstemp(tmp);
    if (fd < 0) {
        return -1;
    }
    size_t off = 0;
    while (off < n) {
        ssize_t w = write(fd, data + off, n - off);
        if (w < 0) {
            close(fd);
            unlink(tmp);
            return -1;
        }
        off += (size_t)w;
    }
    if (fsync(fd) != 0) {
        close(fd);
        unlink(tmp);
        return -1;
    }
    if (close(fd) != 0) {
        unlink(tmp);
        return -1;
    }
    if (rename(tmp, out_path) != 0) {
        unlink(tmp);
        return -1;
    }
    return 0;
}

int write_report(const char *out_path, const char *api_base, const char *run_id,
                 const char *schema_digest, const ReconcileResult *result,
                 char *ledger_digest_out, size_t digest_cap) {
    char *ledger = build_ledger(schema_digest, result);
    if (!ledger) {
        return -1;
    }
    if (sha256_bytes((const unsigned char *)ledger, strlen(ledger),
                     ledger_digest_out, digest_cap) != 0) {
        free(ledger);
        return -1;
    }
    free(ledger);

    json_t *root = json_object();
    json_object_set_new(root, "schema_version", json_integer(2));
    json_object_set_new(root, "producer", json_string("tofmass"));
    json_object_set_new(root, "run_id", json_string(run_id));
    json_object_set_new(root, "api_base", json_string(api_base));
    json_object_set_new(root, "schema_digest", json_string(schema_digest));

    json_t *axis = json_object();
    json_object_set_new(axis, "k", json_real(result->theta.v[0]));
    json_object_set_new(axis, "t0", json_real(result->theta.v[1]));
    json_object_set_new(axis, "q", json_real(result->theta.v[2]));
    json_t *order = json_array();
    json_array_append_new(order, json_string("k"));
    json_array_append_new(order, json_string("t0"));
    json_array_append_new(order, json_string("q"));
    json_object_set_new(axis, "covariance_order", order);
    json_t *cov = json_array();
    for (int i = 0; i < 3; i++) {
        json_t *row = json_array();
        for (int j = 0; j < 3; j++) {
            json_array_append_new(row, json_real(result->cov.m[i][j]));
        }
        json_array_append_new(cov, row);
    }
    json_object_set_new(axis, "covariance", cov);
    json_object_set_new(axis, "source", json_string(result->source));
    json_t *iv = json_array();
    json_array_append_new(iv, json_real(result->interval_lo));
    json_array_append_new(iv, json_real(result->interval_hi));
    json_object_set_new(axis, "monotonic_interval_us", iv);
    json_object_set_new(root, "axis", axis);

    json_t *prov = json_object();
    json_t *used = json_array();
    for (size_t i = 0; i < result->used_count; i++) {
        json_array_append_new(used, json_string(result->used_keys[i]));
    }
    json_object_set_new(prov, "used_candidate_keys", used);
    json_t *rej = json_array();
    for (size_t i = 0; i < result->rejected.count; i++) {
        json_t *e = json_object();
        json_object_set_new(e, "candidate_key",
                            json_string(result->rejected.items[i].candidate_key));
        json_object_set_new(e, "reason",
                            json_string(result->rejected.items[i].reason));
        json_array_append_new(rej, e);
    }
    json_object_set_new(prov, "rejected_candidates", rej);
    json_object_set_new(root, "provenance", prov);

    json_t *peaks = json_array();
    for (size_t i = 0; i < result->peak_count; i++) {
        const PeakResult *p = &result->peaks[i];
        json_t *o = json_object();
        json_object_set_new(o, "peak_id", json_string(p->peak_id));
        json_object_set_new(o, "tof_us", json_real(p->tof_us));
        json_object_set_new(o, "tof_sigma_us", json_real(p->tof_sigma_us));
        json_object_set_new(o, "corrected_da", json_real(p->corrected_da));
        json_object_set_new(o, "sigma_corr_da", json_real(p->sigma_corr_da));
        if (p->has_catalog) {
            json_object_set_new(o, "catalog_id", json_string(p->catalog_id));
            json_object_set_new(o, "catalog_da", json_real(p->catalog_da));
            json_object_set_new(o, "residual_da", json_real(p->residual_da));
            json_object_set_new(o, "z_score", json_real(p->z_score));
        } else {
            json_object_set_new(o, "catalog_id", json_null());
            json_object_set_new(o, "catalog_da", json_null());
            json_object_set_new(o, "residual_da", json_null());
            json_object_set_new(o, "z_score", json_null());
        }
        json_object_set_new(o, "accepted", json_boolean(p->accepted));
        if (p->accepted) {
            json_object_set_new(o, "reject_reason", json_null());
        } else {
            json_object_set_new(o, "reject_reason", json_string(p->reject_reason));
        }
        json_array_append_new(peaks, o);
    }
    json_object_set_new(root, "peaks", peaks);

    json_t *summary = json_object();
    json_object_set_new(summary, "matched", json_integer(result->matched));
    json_object_set_new(summary, "accepted", json_integer(result->accepted));
    json_object_set_new(summary, "rejected", json_integer(result->rejected_count));
    json_object_set_new(summary, "no_match", json_integer(result->no_match));
    json_object_set_new(summary, "outlier", json_integer(result->outlier));
    if (result->has_weighted_rms_z) {
        json_object_set_new(summary, "weighted_rms_z",
                            json_real(result->weighted_rms_z));
    } else {
        json_object_set_new(summary, "weighted_rms_z", json_null());
    }
    if (result->has_max_abs_z) {
        json_object_set_new(summary, "max_abs_z", json_real(result->max_abs_z));
    } else {
        json_object_set_new(summary, "max_abs_z", json_null());
    }
    json_object_set_new(root, "summary", summary);
    json_object_set_new(root, "ledger_digest", json_string(ledger_digest_out));

    char *dump = json_dumps(root, JSON_INDENT(2) | JSON_REAL_PRECISION(17));
    json_decref(root);
    if (!dump) {
        return -1;
    }
    size_t dn = strlen(dump);
    char *with_nl = malloc(dn + 2);
    if (!with_nl) {
        free(dump);
        return -1;
    }
    memcpy(with_nl, dump, dn);
    with_nl[dn] = '\n';
    with_nl[dn + 1] = '\0';
    free(dump);

    int rc = atomic_write(out_path, with_nl, dn + 1);
    free(with_nl);
    return rc;
}

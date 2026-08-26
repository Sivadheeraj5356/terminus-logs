#define _POSIX_C_SOURCE 200809L

#include "feature_audit.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <curl/curl.h>

typedef struct {
    char *data;
    size_t size;
} curl_buffer_t;

typedef struct {
    char digraph_name[128];
    char rankdir[16];
    char pass2_parent_suffix[64];
    char freshness_column[64];
    char pass1_order_dir[8];
    char run_order_dir[8];
    char registry_json_field[64];
    char leak_detail_fmt[256];
    char unapproved_detail_fmt[256];
} graph_binding_t;

/* Deliberately wrong lab defaults — production values must load from binding. */
static graph_binding_t g_graph_binding = {
    .digraph_name = "rejected_training_lineage",
    .rankdir = "LR",
    .pass2_parent_suffix = "_parent",
    .freshness_column = "committed_at",
    .pass1_order_dir = "DESC",
    .run_order_dir = "DESC",
    .registry_json_field = "deployment_approved",
    .leak_detail_fmt = "feature %s posted after cutoff %s",
    .unapproved_detail_fmt = "model %s lacks deployment approval",
};

static size_t append_curl_response(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t chunk = size * nmemb;
    curl_buffer_t *buffer = (curl_buffer_t *)userp;
    char *next = realloc(buffer->data, buffer->size + chunk + 1);

    if (next == NULL) {
        return 0;
    }
    buffer->data = next;
    memcpy(buffer->data + buffer->size, contents, chunk);
    buffer->size += chunk;
    buffer->data[buffer->size] = '\0';
    return chunk;
}

static int run_duckdb_csv(
    const char *db_path,
    const char *sql,
    char *output,
    size_t output_len
) {
    char command[4096];
    FILE *pipe;

    if (output_len == 0) {
        return -1;
    }
    output[0] = '\0';

    snprintf(
        command,
        sizeof(command),
        "duckdb '%s' -csv -noheader -c \"%s\" 2>/dev/null",
        db_path,
        sql
    );
    pipe = popen(command, "r");
    if (pipe == NULL) {
        return -1;
    }

    size_t used = 0;
    char line[1024];
    while (fgets(line, sizeof(line), pipe) != NULL) {
        size_t line_len = strlen(line);
        if (used + line_len + 1 >= output_len) {
            pclose(pipe);
            return -1;
        }
        memcpy(output + used, line, line_len);
        used += line_len;
    }

    if (pclose(pipe) != 0) {
        return -1;
    }
    if (used > 0 && output[used - 1] == '\n') {
        output[used - 1] = '\0';
    } else {
        output[used] = '\0';
    }
    return 0;
}

/* Depth-1 key finder: only matches keys whose enclosing brace depth is 1. */
static const char *find_depth1_key(const char *obj, const char *key) {
    char pattern[80];
    size_t plen;
    int depth = 0;
    int in_str = 0;
    int esc = 0;
    const char *p;

    if (obj == NULL || *obj != '{') {
        return NULL;
    }
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    plen = strlen(pattern);

    for (p = obj; *p != '\0'; p++) {
        char c = *p;
        if (in_str) {
            if (esc) {
                esc = 0;
                continue;
            }
            if (c == '\\') {
                esc = 1;
                continue;
            }
            if (c == '"') {
                in_str = 0;
            }
            continue;
        }
        if (c == '"') {
            if (depth == 1 && strncmp(p, pattern, plen) == 0) {
                const char *after = p + plen;
                while (*after != '\0' && isspace((unsigned char)*after)) {
                    after++;
                }
                if (*after == ':') {
                    return p;
                }
            }
            in_str = 1;
            continue;
        }
        if (c == '{' || c == '[') {
            depth++;
        } else if (c == '}' || c == ']') {
            depth--;
            if (depth == 0) {
                return NULL;
            }
        }
    }
    return NULL;
}

static const char *value_after_key(const char *key_pos) {
    const char *p;

    if (key_pos == NULL) {
        return NULL;
    }
    p = strchr(key_pos, ':');
    if (p == NULL) {
        return NULL;
    }
    p++;
    while (*p != '\0' && isspace((unsigned char)*p)) {
        p++;
    }
    return p;
}

static const char *object_after_key(const char *key_pos) {
    const char *p = value_after_key(key_pos);
    if (p == NULL || *p != '{') {
        return NULL;
    }
    return p;
}

static int extract_string_in_obj(
    const char *obj,
    const char *key,
    char *out,
    size_t out_sz
) {
    const char *k;
    const char *v;
    size_t i;

    k = find_depth1_key(obj, key);
    if (k == NULL) {
        return -1;
    }
    v = value_after_key(k);
    if (v == NULL || *v != '"') {
        return -1;
    }
    v++;
    i = 0;
    while (*v != '\0' && *v != '"' && i + 1 < out_sz) {
        out[i++] = *v++;
    }
    if (*v != '"') {
        return -1;
    }
    out[i] = '\0';
    return 0;
}

static int extract_json_string(
    const char *json,
    const char *key,
    char *out,
    size_t out_len
) {
    char pattern[128];
    const char *start;
    const char *end;

    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    start = strstr(json, pattern);
    if (start == NULL) {
        return -1;
    }
    start = strchr(start, ':');
    if (start == NULL) {
        return -1;
    }
    start = strchr(start, '"');
    if (start == NULL) {
        return -1;
    }
    start += 1;
    end = strchr(start, '"');
    if (end == NULL) {
        return -1;
    }
    size_t len = (size_t)(end - start);
    if (len + 1 > out_len) {
        return -1;
    }
    memcpy(out, start, len);
    out[len] = '\0';
    return 0;
}

/*
 * Convert binding templates to printf formats:
 *   {feature_name}@{feature_version} -> %s  (SQL already yields name@version)
 *   {ledger_cutoff} / {model_name}   -> %s
 */
static void template_to_printf(const char *tmpl, char *fmt, size_t fmt_len) {
    size_t oi = 0;
    const char *p = tmpl;

    while (*p != '\0' && oi + 1 < fmt_len) {
        if (strncmp(p, "{feature_name}@{feature_version}", 32) == 0) {
            if (oi + 2 >= fmt_len) {
                break;
            }
            fmt[oi++] = '%';
            fmt[oi++] = 's';
            p += 32;
            continue;
        }
        if (strncmp(p, "{ledger_cutoff}", 15) == 0) {
            if (oi + 2 >= fmt_len) {
                break;
            }
            fmt[oi++] = '%';
            fmt[oi++] = 's';
            p += 15;
            continue;
        }
        if (strncmp(p, "{model_name}", 12) == 0) {
            if (oi + 2 >= fmt_len) {
                break;
            }
            fmt[oi++] = '%';
            fmt[oi++] = 's';
            p += 12;
            continue;
        }
        if (*p == '%') {
            if (oi + 2 >= fmt_len) {
                break;
            }
            fmt[oi++] = '%';
            fmt[oi++] = '%';
            p++;
            continue;
        }
        fmt[oi++] = *p++;
    }
    fmt[oi] = '\0';
}

static void pass1_order_dir_from_order_by(const char *order_by, char *out, size_t out_len) {
    const char *p = order_by;
    while (*p != '\0' && !isspace((unsigned char)*p)) {
        p++;
    }
    while (*p != '\0' && isspace((unsigned char)*p)) {
        p++;
    }
    if (strncmp(p, "DESC", 4) == 0) {
        snprintf(out, out_len, "%s", "DESC");
    } else {
        snprintf(out, out_len, "%s", "ASC");
    }
}

static void run_order_dir_from_manifest_order(const char *order_by, char *out, size_t out_len) {
    pass1_order_dir_from_order_by(order_by, out, out_len);
}

static int load_graph_binding(void) {
    const char *path;
    FILE *fp;
    char json[65536];
    size_t read_bytes;
    const char *pb_key;
    const char *pb;
    const char *templates_key;
    const char *templates;
    char order_by[128];
    char leak_tmpl[256];
    char unapproved_tmpl[256];

    path = getenv("GRAPH_EMISSION_CONTRACT");
    if (path == NULL || path[0] == '\0') {
        path = "/app/data/graph_emission.prod.json";
    }

    fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }
    read_bytes = fread(json, 1, sizeof(json) - 1, fp);
    fclose(fp);
    json[read_bytes] = '\0';

    /* Root-level production_binding only — counsel_scratch is nested (depth > 1). */
    pb_key = find_depth1_key(json, "production_binding");
    if (pb_key == NULL) {
        return -1;
    }
    pb = object_after_key(pb_key);
    if (pb == NULL) {
        return -1;
    }

    if (extract_string_in_obj(
            pb, "digraph_name", g_graph_binding.digraph_name,
            sizeof(g_graph_binding.digraph_name)) != 0) {
        return -1;
    }
    if (extract_string_in_obj(
            pb, "rankdir", g_graph_binding.rankdir,
            sizeof(g_graph_binding.rankdir)) != 0) {
        return -1;
    }
    if (extract_string_in_obj(
            pb, "pass2_parent_suffix", g_graph_binding.pass2_parent_suffix,
            sizeof(g_graph_binding.pass2_parent_suffix)) != 0) {
        return -1;
    }
    if (extract_string_in_obj(
            pb, "ledger_timestamp_column", g_graph_binding.freshness_column,
            sizeof(g_graph_binding.freshness_column)) != 0) {
        return -1;
    }
    if (extract_string_in_obj(pb, "pass1_feature_order_by", order_by, sizeof(order_by)) != 0) {
        return -1;
    }
    pass1_order_dir_from_order_by(
        order_by, g_graph_binding.pass1_order_dir, sizeof(g_graph_binding.pass1_order_dir)
    );

    if (extract_string_in_obj(pb, "run_manifest_order", order_by, sizeof(order_by)) != 0) {
        return -1;
    }
    run_order_dir_from_manifest_order(
        order_by, g_graph_binding.run_order_dir, sizeof(g_graph_binding.run_order_dir)
    );

    if (extract_string_in_obj(
            pb, "registry_json_field", g_graph_binding.registry_json_field,
            sizeof(g_graph_binding.registry_json_field)) != 0) {
        return -1;
    }

    templates_key = find_depth1_key(pb, "violation_detail_templates");
    if (templates_key == NULL) {
        return -1;
    }
    templates = object_after_key(templates_key);
    if (templates == NULL) {
        return -1;
    }
    if (extract_string_in_obj(templates, "leaking_feature", leak_tmpl, sizeof(leak_tmpl)) != 0) {
        return -1;
    }
    if (extract_string_in_obj(
            templates, "unapproved_model", unapproved_tmpl, sizeof(unapproved_tmpl)) != 0) {
        return -1;
    }
    template_to_printf(
        leak_tmpl, g_graph_binding.leak_detail_fmt, sizeof(g_graph_binding.leak_detail_fmt)
    );
    template_to_printf(
        unapproved_tmpl,
        g_graph_binding.unapproved_detail_fmt,
        sizeof(g_graph_binding.unapproved_detail_fmt)
    );
    return 0;
}

static int json_field_is_true(const char *json, const char *field) {
    char pattern[96];
    const char *start;

    snprintf(pattern, sizeof(pattern), "\"%s\"", field);
    start = strstr(json, pattern);
    if (start == NULL) {
        return 0;
    }
    start = strchr(start, ':');
    if (start == NULL) {
        return 0;
    }
    start += 1;
    while (*start != '\0' && isspace((unsigned char)*start)) {
        start += 1;
    }
    return strncmp(start, "true", 4) == 0;
}

static int fetch_model_approved(const char *registry_base_url, const char *model_name) {
    CURL *curl;
    CURLcode code;
    long http_code = 0;
    char url[512];
    curl_buffer_t response = {NULL, 0};
    int approved = 0;

    snprintf(
        url,
        sizeof(url),
        "%s/v1/models/%s/deployment",
        registry_base_url,
        model_name
    );

    curl = curl_easy_init();
    if (curl == NULL) {
        return -1;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, append_curl_response);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);

    code = curl_easy_perform(curl);
    if (code != CURLE_OK) {
        curl_easy_cleanup(curl);
        free(response.data);
        return -1;
    }

    if (curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code) != CURLE_OK) {
        curl_easy_cleanup(curl);
        free(response.data);
        return -1;
    }

    curl_easy_cleanup(curl);

    if (http_code != 200 || response.data == NULL) {
        free(response.data);
        return 0;
    }

    approved = json_field_is_true(response.data, g_graph_binding.registry_json_field) ? 1 : 0;
    free(response.data);
    return approved;
}

static void append_violation(
    audit_run_result_t *run,
    const char *violation_type,
    const char *detail
) {
    if (run->violation_count >= AUDIT_MAX_VIOLATIONS) {
        return;
    }
    audit_violation_t *slot = &run->violations[run->violation_count++];
    snprintf(slot->violation_type, sizeof(slot->violation_type), "%s", violation_type);
    snprintf(slot->detail, sizeof(slot->detail), "%s", detail);
    run->approved = 0;
}

static int feature_has_leaking_violation(
    const audit_run_result_t *run,
    const char *feature_name
) {
    int i;

    for (i = 0; i < run->violation_count; i++) {
        const audit_violation_t *violation = &run->violations[i];
        char feature_at_version[128];
        char *at_sign;

        if (strcmp(violation->violation_type, "leaking_feature") != 0) {
            continue;
        }
        if (sscanf(violation->detail, "feature %127[^ ]", feature_at_version) != 1) {
            continue;
        }
        at_sign = strchr(feature_at_version, '@');
        if (at_sign != NULL) {
            *at_sign = '\0';
        }
        if (strcmp(feature_at_version, feature_name) == 0) {
            return 1;
        }
    }
    return 0;
}

static int run_has_unapproved_violation(const audit_run_result_t *run) {
    int i;

    for (i = 0; i < run->violation_count; i++) {
        if (strcmp(run->violations[i].violation_type, "unapproved_model") == 0) {
            return 1;
        }
    }
    return 0;
}

static int audit_single_run(
    const char *db_path,
    const char *ledger_cutoff,
    const char *registry_base_url,
    audit_run_result_t *run
) {
    char sql[2048];
    char buffer[8192];
    char *cursor;
    char *saveptr;
    int approval_status;

    run->approved = 1;
    run->violation_count = 0;

    snprintf(
        sql,
        sizeof(sql),
        "SELECT rf.feature_name || '@' || rf.feature_version "
        "FROM run_features rf "
        "JOIN feature_ledger fl "
        "  ON rf.feature_name = fl.feature_name "
        " AND rf.feature_version = fl.feature_version "
        "WHERE rf.run_id = '%s' "
        "  AND fl.%s > TIMESTAMP '%s' "
        "ORDER BY rf.feature_name, rf.feature_version",
        run->run_id,
        g_graph_binding.freshness_column,
        ledger_cutoff
    );
    if (run_duckdb_csv(db_path, sql, buffer, sizeof(buffer)) == 0 && buffer[0] != '\0') {
        cursor = buffer;
        saveptr = NULL;
        while ((cursor = strtok_r(cursor, "\n", &saveptr)) != NULL) {
            char detail[AUDIT_LINE_LEN];
            snprintf(
                detail,
                sizeof(detail),
                g_graph_binding.leak_detail_fmt,
                cursor,
                ledger_cutoff
            );
            append_violation(run, "leaking_feature", detail);
            cursor = NULL;
        }
    }

    approval_status = fetch_model_approved(registry_base_url, run->model_name);
    if (approval_status < 0) {
        return -1;
    }
    if (approval_status == 0) {
        char detail[AUDIT_LINE_LEN];
        snprintf(
            detail,
            sizeof(detail),
            g_graph_binding.unapproved_detail_fmt,
            run->model_name
        );
        append_violation(run, "unapproved_model", detail);
    }

    if (run->violation_count == 0) {
        run->approved = 1;
    }

    return 0;
}

int audit_load_policy(const char *policy_path, audit_report_t *report) {
    FILE *fp;
    char json[4096];
    size_t read_bytes;

    fp = fopen(policy_path, "r");
    if (fp == NULL) {
        return -1;
    }
    read_bytes = fread(json, 1, sizeof(json) - 1, fp);
    fclose(fp);
    json[read_bytes] = '\0';

    if (extract_json_string(
            json,
            "policy_version",
            report->policy_version,
            sizeof(report->policy_version)) != 0) {
        return -1;
    }
    if (extract_json_string(
            json,
            "ledger_cutoff",
            report->ledger_cutoff,
            sizeof(report->ledger_cutoff)) != 0) {
        return -1;
    }
    if (extract_json_string(
            json,
            "registry_base_url",
            report->registry_base_url,
            sizeof(report->registry_base_url)) != 0) {
        return -1;
    }
    report->run_count = 0;
    return 0;
}

int audit_all_runs(
    const char *db_path,
    const char *policy_path,
    const char *output_dir,
    audit_report_t *report
) {
    char sql[512];
    char buffer[2048];
    char *cursor;
    char *saveptr;

    (void)output_dir;

    if (load_graph_binding() != 0) {
        return -1;
    }

    if (audit_load_policy(policy_path, report) != 0) {
        return -1;
    }

    snprintf(
        sql,
        sizeof(sql),
        "SELECT run_id, model_name FROM run_manifest ORDER BY run_id %s",
        g_graph_binding.run_order_dir
    );
    if (run_duckdb_csv(db_path, sql, buffer, sizeof(buffer)) != 0) {
        return -1;
    }

    report->run_count = 0;
    cursor = buffer;
    saveptr = NULL;
    while ((cursor = strtok_r(cursor, "\n", &saveptr)) != NULL) {
        char *comma;
        audit_run_result_t *run;

        if (report->run_count >= AUDIT_MAX_RUNS) {
            break;
        }

        comma = strchr(cursor, ',');
        if (comma == NULL) {
            return -1;
        }
        *comma = '\0';

        run = &report->runs[report->run_count++];
        snprintf(run->run_id, sizeof(run->run_id), "%s", cursor);
        snprintf(run->model_name, sizeof(run->model_name), "%s", comma + 1);

        if (audit_single_run(
                db_path,
                report->ledger_cutoff,
                report->registry_base_url,
                run) != 0) {
            return -1;
        }
        cursor = NULL;
    }
    return 0;
}

static int write_compliance_contract(const char *output_dir) {
    char path[512];
    char manifest[4096];
    char marker[256];
    FILE *fp;
    size_t n;

    fp = fopen("/app/data/governance_manifest.json", "r");
    if (fp == NULL) {
        return -1;
    }
    n = fread(manifest, 1, sizeof(manifest) - 1, fp);
    fclose(fp);
    manifest[n] = '\0';
    if (extract_json_string(manifest, "binding_marker", marker, sizeof(marker)) != 0) {
        return -1;
    }

    snprintf(path, sizeof(path), "%s/training_compliance_contract.md", output_dir);
    fp = fopen(path, "w");
    if (fp == NULL) {
        return -1;
    }

    /* Live digraph + freshness from production_binding; re-emitted on every evaluate. */
    fprintf(
        fp,
        "# Training Run Compliance Contract\n"
        "\n"
        "Production behavior resolves from `governance_manifest.json`, "
        "`training_compliance_annex.md`, counsel-closure ledger 0091, "
        "post-closure ledger 0093, and the ledger 0093-selected "
        "`graph_emission.prod.json` under the %s binding marker.\n"
        "\n"
        "## Violation taxonomy\n"
        "\n"
        "The evaluator emits only `leaking_feature` and `unapproved_model` "
        "violation literals in verdict JSON, findings CSV, and graph xlabels.\n"
        "\n"
        "## Ledger 0091 — freshness and registry\n"
        "\n"
        "Compare `feature_ledger.%s` against policy cutoff; pipeline ingest "
        "metadata (`committed_at`) is informational only. Registry gate reads "
        "root `approved` from deployment GET responses "
        "(ignore legacy `deployment_approved`).\n"
        "\n"
        "## Ledger 0093 — graph emission\n"
        "\n"
        "Two-pass rejected-run Graphviz digraph `%s` with child-to-parent "
        "lineage edges, parent reference nodes, and bare feature-name labels "
        "per root `production_binding` in `graph_emission.prod.json`.\n",
        marker,
        g_graph_binding.freshness_column,
        g_graph_binding.digraph_name
    );
    fclose(fp);
    return 0;
}

int audit_write_report(const char *output_dir, const audit_report_t *report) {
    char path[512];
    FILE *fp;
    int i;
    int j;

    snprintf(path, sizeof(path), "%s/training_run_verdicts.json", output_dir);
    fp = fopen(path, "w");
    if (fp == NULL) {
        return -1;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"policy_version\": \"%s\",\n", report->policy_version);
    fprintf(fp, "  \"ledger_cutoff\": \"%s\",\n", report->ledger_cutoff);
    fprintf(fp, "  \"registry_base_url\": \"%s\",\n", report->registry_base_url);
    fprintf(fp, "  \"runs\": [\n");
    for (i = 0; i < report->run_count; i++) {
        const audit_run_result_t *run = &report->runs[i];
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"run_id\": \"%s\",\n", run->run_id);
        fprintf(fp, "      \"model_name\": \"%s\",\n", run->model_name);
        fprintf(fp, "      \"approved\": %s,\n", run->approved ? "true" : "false");
        fprintf(fp, "      \"violations\": [\n");
        for (j = 0; j < run->violation_count; j++) {
            const audit_violation_t *violation = &run->violations[j];
            fprintf(fp, "        {\n");
            fprintf(
                fp,
                "          \"violation_type\": \"%s\",\n",
                violation->violation_type
            );
            fprintf(fp, "          \"detail\": \"%s\"\n", violation->detail);
            fprintf(fp, "        }%s\n", (j + 1 < run->violation_count) ? "," : "");
        }
        fprintf(fp, "      ]\n");
        fprintf(fp, "    }%s\n", (i + 1 < report->run_count) ? "," : "");
    }
    fprintf(fp, "  ]\n");
    fprintf(fp, "}\n");
    fclose(fp);

    if (write_compliance_contract(output_dir) != 0) {
        return -1;
    }
    return 0;
}

int audit_write_violations_csv(const char *output_dir, const audit_report_t *report) {
    char path[512];
    FILE *fp;
    int i;
    int j;

    snprintf(path, sizeof(path), "%s/leakage_findings.csv", output_dir);
    fp = fopen(path, "w");
    if (fp == NULL) {
        return -1;
    }

    fprintf(fp, "run_id,violation_type,detail\n");
    for (i = 0; i < report->run_count; i++) {
        const audit_run_result_t *run = &report->runs[i];
        for (j = 0; j < run->violation_count; j++) {
            const audit_violation_t *violation = &run->violations[j];
            fprintf(
                fp,
                "%s,%s,%s\n",
                run->run_id,
                violation->violation_type,
                violation->detail
            );
        }
    }
    fclose(fp);
    return 0;
}

int audit_write_lineage_graph(
    const char *db_path,
    const char *output_dir,
    const audit_report_t *report
) {
    char path[512];
    char sql[2048];
    char buffer[16384];
    FILE *fp;
    int i;

    snprintf(path, sizeof(path), "%s/rejected_run_lineage.dot", output_dir);
    fp = fopen(path, "w");
    if (fp == NULL) {
        return -1;
    }

    fprintf(fp, "digraph %s {\n", g_graph_binding.digraph_name);
    fprintf(fp, "  rankdir=%s;\n", g_graph_binding.rankdir);

    for (i = 0; i < report->run_count; i++) {
        const audit_run_result_t *run = &report->runs[i];
        char run_node_id[128];

        if (run->approved) {
            continue;
        }

        snprintf(run_node_id, sizeof(run_node_id), "%s_run", run->run_id);

        fprintf(fp, "  subgraph cluster_%s {\n", run->run_id);
        fprintf(fp, "    label=\"%s\";\n", run->run_id);
        if (run_has_unapproved_violation(run)) {
            fprintf(
                fp,
                "    \"%s\" [shape=box, label=\"%s\", xlabel=\"VIOLATION: unapproved_model\"];\n",
                run_node_id,
                run->run_id
            );
        } else {
            fprintf(
                fp,
                "    \"%s\" [shape=box, label=\"%s\"];\n",
                run_node_id,
                run->run_id
            );
        }

        snprintf(
            sql,
            sizeof(sql),
            "SELECT rf.feature_name "
            "FROM run_features rf "
            "WHERE rf.run_id = '%s' "
            "ORDER BY rf.feature_name %s",
            run->run_id,
            g_graph_binding.pass1_order_dir
        );
        if (run_duckdb_csv(db_path, sql, buffer, sizeof(buffer)) == 0) {
            char *cursor = buffer;
            char *saveptr = NULL;

            while ((cursor = strtok_r(cursor, "\n", &saveptr)) != NULL) {
                char node_id[128];
                snprintf(node_id, sizeof(node_id), "%s_%s", run->run_id, cursor);
                if (feature_has_leaking_violation(run, cursor)) {
                    fprintf(
                        fp,
                        "    \"%s\" [shape=ellipse, label=\"%s\", xlabel=\"VIOLATION: leaking_feature\"];\n",
                        node_id,
                        cursor
                    );
                } else {
                    fprintf(
                        fp,
                        "    \"%s\" [shape=ellipse, label=\"%s\"];\n",
                        node_id,
                        cursor
                    );
                }
                fprintf(fp, "    \"%s\" -> \"%s\";\n", run_node_id, node_id);
                cursor = NULL;
            }
        }

        snprintf(
            sql,
            sizeof(sql),
            "SELECT le.child_feature, le.parent_feature "
            "FROM lineage_edges le "
            "JOIN run_features rf ON rf.feature_name = le.child_feature "
            "WHERE rf.run_id = '%s' "
            "ORDER BY le.child_feature, le.parent_feature",
            run->run_id
        );
        if (run_duckdb_csv(db_path, sql, buffer, sizeof(buffer)) == 0) {
            char *edge_cursor = buffer;
            char *edge_saveptr = NULL;

            while ((edge_cursor = strtok_r(edge_cursor, "\n", &edge_saveptr)) != NULL) {
                char child[128];
                char parent[128];
                char child_id[160];
                char parent_id[160];
                char *comma = strchr(edge_cursor, ',');

                if (comma == NULL) {
                    edge_cursor = NULL;
                    continue;
                }
                *comma = '\0';
                snprintf(child, sizeof(child), "%s", edge_cursor);
                snprintf(parent, sizeof(parent), "%s", comma + 1);
                snprintf(child_id, sizeof(child_id), "%s_%s", run->run_id, child);
                snprintf(
                    parent_id,
                    sizeof(parent_id),
                    "%s_%s%s",
                    run->run_id,
                    parent,
                    g_graph_binding.pass2_parent_suffix
                );
                fprintf(
                    fp,
                    "    \"%s\" [shape=box, label=\"%s\"];\n",
                    parent_id,
                    parent
                );
                fprintf(fp, "    \"%s\" -> \"%s\";\n", child_id, parent_id);
                edge_cursor = NULL;
            }
        }

        fprintf(fp, "  }\n");
    }

    fprintf(fp, "}\n");
    fclose(fp);
    return 0;
}

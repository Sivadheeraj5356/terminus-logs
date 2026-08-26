#define _POSIX_C_SOURCE 200809L

/* Implement training-run compliance evaluator per governance_manifest dossier chain. */

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

static int json_approved_is_true(const char *json) {
    const char *start = strstr(json, "\"approved\"");
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

static int json_deployment_approved(const char *json) {
    const char *start = strstr(json, "\"deployment_approved\"");
    if (start == NULL) {
        return 1;
    }
    start = strchr(start, ':');
    if (start == NULL) {
        return 1;
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

    approved = json_approved_is_true(response.data) ? 1 : 0;
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
        "SELECT rf.feature_name "
        "FROM run_features rf "
        "JOIN feature_ledger fl "
        "  ON rf.feature_name = fl.feature_name "
        " AND rf.feature_version = fl.feature_version "
        "WHERE rf.run_id = '%s' "
        "  AND fl.committed_at > TIMESTAMP '%s'",
        run->run_id,
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
                "feature %s ledger_as_of after cutoff %s",
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
            "model %s registry approved false",
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

    if (audit_load_policy(policy_path, report) != 0) {
        return -1;
    }

    snprintf(
        sql,
        sizeof(sql),
        "SELECT run_id, model_name FROM run_manifest ORDER BY run_id DESC"
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

    fprintf(fp, "digraph rejected_training_lineage {\n");
    fprintf(fp, "  rankdir=LR;\n");

    for (i = 0; i < report->run_count; i++) {
        const audit_run_result_t *run = &report->runs[i];
        char run_node_id[128];

        if (run->approved) {
            continue;
        }

        snprintf(run_node_id, sizeof(run_node_id), "%s_run", run->run_id);

        fprintf(fp, "  subgraph cluster_%s {\n", run->run_id);
        fprintf(fp, "    label=\"%s\";\n", run->run_id);
        fprintf(
            fp,
            "    \"%s\" [shape=box, label=\"%s\"];\n",
            run_node_id,
            run->run_id
        );

        snprintf(
            sql,
            sizeof(sql),
            "SELECT rf.feature_name "
            "FROM run_features rf "
            "WHERE rf.run_id = '%s'",
            run->run_id
        );
        if (run_duckdb_csv(db_path, sql, buffer, sizeof(buffer)) == 0) {
            char *cursor = buffer;
            char *saveptr = NULL;

            while ((cursor = strtok_r(cursor, "\n", &saveptr)) != NULL) {
                char node_id[128];
                snprintf(node_id, sizeof(node_id), "%s_%s", run->run_id, cursor);
                fprintf(
                    fp,
                    "    \"%s\" [shape=ellipse, label=\"%s\"];\n",
                    node_id,
                    cursor
                );
                fprintf(fp, "    \"%s\" -> \"%s\";\n", run_node_id, node_id);
                cursor = NULL;
            }
        }

        fprintf(fp, "  }\n");
    }

    fprintf(fp, "}\n");
    fclose(fp);
    return 0;
}

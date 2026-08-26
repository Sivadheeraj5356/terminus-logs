#include "http.h"
#include "markdown.h"
#include "reconcile.h"
#include "report.h"

#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *argv0) {
    fprintf(stderr,
            "usage: %s --api URL --run-id ID --notes DIR --schema FILE --out FILE\n",
            argv0);
}

int main(int argc, char **argv) {
    const char *api = NULL;
    const char *run_id = NULL;
    const char *notes = NULL;
    const char *schema = NULL;
    const char *out = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--api") == 0 && i + 1 < argc) {
            api = argv[++i];
        } else if (strcmp(argv[i], "--run-id") == 0 && i + 1 < argc) {
            run_id = argv[++i];
        } else if (strcmp(argv[i], "--notes") == 0 && i + 1 < argc) {
            notes = argv[++i];
        } else if (strcmp(argv[i], "--schema") == 0 && i + 1 < argc) {
            schema = argv[++i];
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            out = argv[++i];
        } else {
            usage(argv[0]);
            return 2;
        }
    }

    if (!api || !run_id || !notes || !schema || !out) {
        usage(argv[0]);
        return 2;
    }

    char schema_digest[65];
    if (schema_bind(schema, schema_digest, sizeof(schema_digest)) != 0) {
        fprintf(stderr, "schema binding failed\n");
        return 1;
    }

    curl_global_init(CURL_GLOBAL_DEFAULT);

    char url[1024];
    snprintf(url, sizeof(url), "%s/health", api);
    json_t *health = http_get_json(url);
    if (!health) {
        fprintf(stderr, "health check failed\n");
        curl_global_cleanup();
        return 1;
    }
    json_decref(health);

    snprintf(url, sizeof(url), "%s/v1/runs/%s/calibration", api, run_id);
    json_t *cal = http_get_json(url);
    snprintf(url, sizeof(url), "%s/v1/runs/%s/peaks", api, run_id);
    json_t *peaks = http_get_json(url);
    snprintf(url, sizeof(url), "%s/v1/catalog/ions", api);
    json_t *catalog = http_get_json(url);
    if (!cal || !peaks || !catalog) {
        fprintf(stderr, "API fetch failed\n");
        json_decref(cal);
        json_decref(peaks);
        json_decref(catalog);
        curl_global_cleanup();
        return 1;
    }

    LabCandidateList labs;
    RejectedList parse_rejected;
    lab_list_init(&labs);
    rejected_list_init(&parse_rejected);
    if (parse_lab_notes(notes, &labs, &parse_rejected) != 0) {
        fprintf(stderr, "lab note parse failed\n");
        json_decref(cal);
        json_decref(peaks);
        json_decref(catalog);
        lab_list_free(&labs);
        rejected_list_free(&parse_rejected);
        curl_global_cleanup();
        return 1;
    }

    ReconcileResult result;
    if (reconcile_run(run_id, cal, peaks, catalog, &labs, &parse_rejected,
                      &result) != 0) {
        fprintf(stderr, "reconcile failed\n");
        json_decref(cal);
        json_decref(peaks);
        json_decref(catalog);
        lab_list_free(&labs);
        rejected_list_free(&parse_rejected);
        curl_global_cleanup();
        return 1;
    }

    char digest[65];
    if (write_report(out, api, run_id, schema_digest, &result, digest,
                     sizeof(digest)) != 0) {
        fprintf(stderr, "report write failed\n");
        reconcile_result_free(&result);
        json_decref(cal);
        json_decref(peaks);
        json_decref(catalog);
        lab_list_free(&labs);
        rejected_list_free(&parse_rejected);
        curl_global_cleanup();
        return 1;
    }

    printf("wrote %s digest=%s\n", out, digest);

    reconcile_result_free(&result);
    json_decref(cal);
    json_decref(peaks);
    json_decref(catalog);
    lab_list_free(&labs);
    rejected_list_free(&parse_rejected);
    curl_global_cleanup();
    return 0;
}

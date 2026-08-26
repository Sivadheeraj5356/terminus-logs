#include "feature_audit.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *argv0) {
    fprintf(
        stderr,
        "Usage: %s --evaluate-training-runs --db /app/data/lineage.duckdb "
        "--policy /app/data/governance_policy.json "
        "--output /app/output\n",
        argv0
    );
}

int main(int argc, char **argv) {
    const char *db_path = NULL;
    const char *policy_path = NULL;
    const char *output_dir = NULL;
    int evaluate = 0;
    audit_report_t report;
    int i;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--evaluate-training-runs") == 0) {
            evaluate = 1;
        } else if (strcmp(argv[i], "--db") == 0 && i + 1 < argc) {
            db_path = argv[++i];
        } else if (strcmp(argv[i], "--policy") == 0 && i + 1 < argc) {
            policy_path = argv[++i];
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            output_dir = argv[++i];
        } else {
            usage(argv[0]);
            return 1;
        }
    }

    if (!evaluate || db_path == NULL || policy_path == NULL || output_dir == NULL) {
        usage(argv[0]);
        return 1;
    }

    if (audit_all_runs(db_path, policy_path, output_dir, &report) != 0) {
        fprintf(stderr, "training-run evaluation failed\n");
        return 1;
    }
    if (audit_write_report(output_dir, &report) != 0) {
        fprintf(stderr, "failed to write training_run_verdicts.json\n");
        return 1;
    }
    if (audit_write_violations_csv(output_dir, &report) != 0) {
        fprintf(stderr, "failed to write leakage_findings.csv\n");
        return 1;
    }
    if (audit_write_lineage_graph(db_path, output_dir, &report) != 0) {
        fprintf(stderr, "failed to write rejected_run_lineage.dot\n");
        return 1;
    }

    return 0;
}

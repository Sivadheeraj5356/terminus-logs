#ifndef FEATURE_AUDIT_H
#define FEATURE_AUDIT_H

#include <stddef.h>

#define AUDIT_MAX_RUNS 16
#define AUDIT_MAX_VIOLATIONS 32
#define AUDIT_LINE_LEN 512

typedef struct {
    char violation_type[64];
    char detail[AUDIT_LINE_LEN];
} audit_violation_t;

typedef struct {
    char run_id[64];
    char model_name[128];
    int approved;
    int violation_count;
    audit_violation_t violations[AUDIT_MAX_VIOLATIONS];
} audit_run_result_t;

typedef struct {
    char policy_version[64];
    char ledger_cutoff[64];
    char registry_base_url[256];
    int run_count;
    audit_run_result_t runs[AUDIT_MAX_RUNS];
} audit_report_t;

int audit_load_policy(const char *policy_path, audit_report_t *report);
int audit_all_runs(
    const char *db_path,
    const char *policy_path,
    const char *output_dir,
    audit_report_t *report
);
int audit_write_report(const char *output_dir, const audit_report_t *report);
int audit_write_violations_csv(const char *output_dir, const audit_report_t *report);
int audit_write_lineage_graph(
    const char *db_path,
    const char *output_dir,
    const audit_report_t *report
);

#endif

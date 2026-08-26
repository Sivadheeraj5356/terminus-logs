#include <stddef.h>

int decide_sweep(const char *frag_path, int boot_gap, int recovery_mode, int *exec_out);
int reconcile_key(const char *rows_path, char *key_out, size_t cap);

int emit_resume(const char *zone, int cadence, const char *trace, const char *out_dir,
                int *row_count);

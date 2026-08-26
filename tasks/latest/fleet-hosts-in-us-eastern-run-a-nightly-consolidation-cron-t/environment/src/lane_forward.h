#include <stddef.h>

int hour_exists(const char *zone, int hour_slot, int *exists_out);
int reconcile_key(const char *rows_path, char *key_out, size_t cap);
void report_hour_table(const char *zone);

int emit_forward(const char *zone, int cadence, const char *trace, const char *out_dir,
                 int *row_count);

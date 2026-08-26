#ifndef NEXT_FIRE_H
#define NEXT_FIRE_H

#include <stdint.h>

#define CADENCE_SEC 86400
#define REPEAT_SLOT 3600

void bind_slot_state(const char *out_dir);
int compute_next_fire(const char *zone, int64_t anchor, int64_t *next_out);
void log_fire_audit(int64_t anchor, int64_t nxt);

#endif

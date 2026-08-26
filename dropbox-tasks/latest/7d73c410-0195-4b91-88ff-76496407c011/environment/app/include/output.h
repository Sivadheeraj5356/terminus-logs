#ifndef OUTPUT_H
#define OUTPUT_H

#include "recover.h"

int write_events_json(const char *path, const RecoveryResult *result);
int write_events_sqlite(const char *path, const RecoveryResult *result);

#endif

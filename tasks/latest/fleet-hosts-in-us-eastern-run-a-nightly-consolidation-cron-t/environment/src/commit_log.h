#ifndef COMMIT_LOG_H
#define COMMIT_LOG_H

#include <stddef.h>

#define COMMIT_LOG_PATH "/app/output/step/commit_log.tab"

int commit_log_append(const char *path, const char *window, const char *key, int seq, int flags);
int commit_log_has_key(const char *path, const char *key);
int commit_log_finest_for_day(const char *path, const char *day8, char *out, size_t cap);

#endif

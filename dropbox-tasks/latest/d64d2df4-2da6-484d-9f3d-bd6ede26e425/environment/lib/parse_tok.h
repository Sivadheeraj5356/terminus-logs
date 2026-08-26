#ifndef PARSE_PATH_H
#define PARSE_PATH_H

#include <stddef.h>

int pp_env_value(const char *path, const char *key, char *out, size_t cap);
int pp_token_count(const char *line);

#endif

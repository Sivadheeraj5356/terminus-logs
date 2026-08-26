#ifndef AC_JSON_H
#define AC_JSON_H

#include "ac_types.h"

int ac_write_formant_json(const char *path, const ac_formant_report *rep);
int ac_write_summary_json(const char *path, const char **profiles, int n);

#endif

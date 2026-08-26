#ifndef TRANSPORT_CONFIG_H
#define TRANSPORT_CONFIG_H

#include "model.h"

/* Read the JSON run description at `path` and populate `m`. Returns 0 on
 * success and non-zero if the file cannot be read. Individual malformed fields
 * abort the program through the json layer. */
int config_load(const char *path, Model *m);

#endif /* TRANSPORT_CONFIG_H */

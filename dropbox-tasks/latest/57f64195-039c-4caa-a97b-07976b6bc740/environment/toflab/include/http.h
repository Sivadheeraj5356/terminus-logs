#ifndef TOFLAB_HTTP_H
#define TOFLAB_HTTP_H

#include <jansson.h>

json_t *http_get_json(const char *url);

#endif

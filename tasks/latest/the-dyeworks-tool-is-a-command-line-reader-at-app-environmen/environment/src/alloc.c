#include "dyeworks/alloc.h"

#include <stdlib.h>

#include "dyeworks/error.h"

/* Allocates the node record table. The byte size is the unit's declared node
 * count times the per-record stride. */
dyeworks_node_t *node_alloc(uint32_t count) {
    uint32_t total = count * (uint32_t)sizeof(dyeworks_node_t);
    void *p = malloc(total ? total : 1);
    if (!p) {
        dyeworks_error("node", "cannot allocate node table");
        return NULL;
    }
    return (dyeworks_node_t *)p;
}

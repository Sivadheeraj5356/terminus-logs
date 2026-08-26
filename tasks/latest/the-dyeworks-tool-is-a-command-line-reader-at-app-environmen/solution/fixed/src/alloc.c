#include "dyeworks/alloc.h"

#include <stdint.h>
#include <stdlib.h>

#include "dyeworks/error.h"

/* Allocates the node record table. The byte size is the unit's declared node
 * count times the per-record stride. */
dyeworks_node_t *node_alloc(uint32_t count) {
    if (count > UINT32_MAX / sizeof(dyeworks_node_t)) {
        dyeworks_error("node", "node count %u overflows the table size", count);
        return NULL;
    }
    size_t total = (size_t)count * sizeof(dyeworks_node_t);
    void *p = malloc(total ? total : 1);
    if (!p) {
        dyeworks_error("node", "cannot allocate node table");
        return NULL;
    }
    return (dyeworks_node_t *)p;
}

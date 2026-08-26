#ifndef DYEWORKS_TYPES_H
#define DYEWORKS_TYPES_H

#include <stddef.h>
#include <stdint.h>

#define DYEWORKS_MAGIC 0x44594557u /* bytes "DYEW" read big-endian */
#define DYEWORKS_NSECTIONS 4

/* Section name codes carried in the section table. */
#define DYEWORKS_SEC_DYEWORKSDEFS 0
#define DYEWORKS_SEC_NODES 1
#define DYEWORKS_SEC_LOTS 2
#define DYEWORKS_SEC_STR 3

/* One {key, form} pair from a dyeworksdef declaration. */
typedef struct {
    uint64_t key;
    uint64_t form;
} dyeworks_field_t;

/* One dyeworks-type declaration from the dyeworksdef schema: a type code, the dyeworks
 * type it names, whether nodes of this type carry children, and the list of
 * key/form pairs that drive how a node's bytes are read. */
typedef struct {
    uint64_t code;
    uint64_t type;
    uint8_t has_children;
    dyeworks_field_t *fields;
    uint32_t nfields;
} dyeworks_def_t;

/* One parsed dyeworks-tree node record. */
typedef struct {
    uint64_t type;
    uint8_t has_children;
} dyeworks_node_t;

/* A located section: its byte offset and size inside the container file. */
typedef struct {
    size_t off;
    size_t size;
    int present;
} dyeworks_section_t;

typedef struct {
    const uint8_t *buf;
    size_t n;

    uint8_t version; /* container version */

    dyeworks_section_t sec[DYEWORKS_NSECTIONS]; /* indexed by section name code */

    dyeworks_def_t *defs;
    uint32_t ndefs;

    uint16_t unit_version;
    uint32_t dyeworksdef_offset;
    uint32_t node_count;
    size_t node_start;
    size_t unit_end;

    dyeworks_node_t *nodes;
    uint32_t nnodes;
    uint64_t root_type;
    int have_root;

    uint32_t lots_resolved;
    uint32_t indirects_resolved;
} dyeworks_t;

#endif

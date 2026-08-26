#include "dyeworks/json_writer.h"

#include "dyeworks/typename.h"

void json_write_summary(FILE *out, const dyeworks_t *sp) {
    fprintf(out,
            "{\"version\":%u,\"dyeworksdefs_defined\":%u,\"nodes_parsed\":%u,"
            "\"lots_resolved\":%u,\"indirects_resolved\":%u,"
            "\"root_type\":\"%s\"}\n",
            (unsigned)sp->unit_version, (unsigned)sp->ndefs,
            (unsigned)sp->nnodes, (unsigned)sp->lots_resolved,
            (unsigned)sp->indirects_resolved, type_name(sp->root_type));
}

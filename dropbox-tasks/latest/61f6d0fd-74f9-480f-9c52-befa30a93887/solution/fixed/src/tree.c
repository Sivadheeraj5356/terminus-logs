#include "dyeworks/tree.h"

#include "dyeworks/alloc.h"
#include "dyeworks/error.h"
#include "dyeworks/form.h"
#include "dyeworks/dyeworksdef.h"
#include "dyeworks/uleb.h"

/* Deepest legitimate node tree; a chain deeper than this is a hostile
 * deep tree, so bounding it keeps the recursive walk below from running
 * the stack off its end on a crafted file. */
#define DYEWORKS_MAX_DEPTH 256

/* Parse one sibling chain of nodes. Each node starts with a type code that
 * selects a dyeworksdef; that declaration's key/form list then drives how many of
 * the node's bytes belong to it. A zero code is a null node that ends the
 * sibling chain. A node whose declaration carries children is followed by its
 * own child sibling chain, parsed recursively. The first real node is the
 * dyeworks tree's root. */
static int parse_siblings(dyeworks_t *sp, size_t *p, uint32_t *idx, uint32_t depth) {
    if (depth > DYEWORKS_MAX_DEPTH) {
        return dyeworks_error("node", "node tree nested too deep");
    }
    const uint8_t *b = sp->buf;

    while (*p < sp->unit_end) {
        uint64_t code;
        size_t used;
        if (uleb_decode(b, *p, sp->unit_end, &code, &used) < 0) {
            return -1;
        }
        *p += used;
        if (code == 0) {
            return 0; /* null node ends this sibling chain */
        }

        const dyeworks_def_t *def = dyeworksdef_lookup(sp, code);
        if (!def) {
            return dyeworks_error("dyeworksdef", "node names unknown type code %llu",
                               (unsigned long long)code);
        }

        for (uint32_t a = 0; a < def->nfields; a++) {
            if (form_consume(sp, def->fields[a].form, p, sp->unit_end) < 0) {
                return -1;
            }
        }

        if (*idx >= sp->node_count) {
            return dyeworks_error("node", "more nodes than the declared count %u",
                               (unsigned)sp->node_count);
        }
        sp->nodes[*idx].type = def->type;
        sp->nodes[*idx].has_children = def->has_children;
        if (!sp->have_root) {
            sp->root_type = def->type;
            sp->have_root = 1;
        }
        (*idx)++;

        if (def->has_children) {
            if (parse_siblings(sp, p, idx, depth + 1) < 0) {
                return -1;
            }
        }
    }

    /* A child sibling chain must be closed by an explicit null node so its
     * parent knows where the children end; reaching the unit end without one
     * means the chain was truncated. The outermost chain (depth zero) legitimately
     * ends where the unit does. */
    if (depth > 0) {
        return dyeworks_error("node",
                           "child node chain reached end of unit without a null terminator");
    }
    return 0;
}

int tree_parse(dyeworks_t *sp) {
    sp->nodes = node_alloc(sp->node_count);
    if (!sp->nodes) {
        return -1;
    }

    size_t p = sp->node_start;
    uint32_t idx = 0;
    if (parse_siblings(sp, &p, &idx, 0) < 0) {
        return -1;
    }

    sp->nnodes = idx;
    return 0;
}

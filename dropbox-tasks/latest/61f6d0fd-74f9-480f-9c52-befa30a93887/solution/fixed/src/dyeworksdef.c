#include "dyeworks/dyeworksdef.h"

#include <stdlib.h>

#include "dyeworks/error.h"
#include "dyeworks/uleb.h"

/* The dyeworksdef section is a sequence of dyeworks-type declarations. Each one is a
 * type code (ULEB128), a dyeworks type (ULEB128), a has-children byte, and a list
 * of {key, form} pairs terminated by a {0, 0} pair. The list of declarations
 * itself ends at a declaration whose type code is zero. */

static int push_field(dyeworks_def_t *d, uint64_t key, uint64_t form) {
    dyeworks_field_t *grown =
        realloc(d->fields, (size_t)(d->nfields + 1) * sizeof(dyeworks_field_t));
    if (!grown) {
        return dyeworks_error("dyeworksdef", "cannot grow field list");
    }
    d->fields = grown;
    d->fields[d->nfields].key = key;
    d->fields[d->nfields].form = form;
    d->nfields++;
    return 0;
}

static int push_def(dyeworks_t *sp, dyeworks_def_t def) {
    dyeworks_def_t *grown =
        realloc(sp->defs, (size_t)(sp->ndefs + 1) * sizeof(dyeworks_def_t));
    if (!grown) {
        return dyeworks_error("dyeworksdef", "cannot grow dyeworksdef table");
    }
    sp->defs = grown;
    sp->defs[sp->ndefs] = def;
    sp->ndefs++;
    return 0;
}

int dyeworksdef_parse(dyeworks_t *sp) {
    const uint8_t *b = sp->buf;
    size_t p = sp->sec[DYEWORKS_SEC_DYEWORKSDEFS].off;
    size_t end =
        sp->sec[DYEWORKS_SEC_DYEWORKSDEFS].off + sp->sec[DYEWORKS_SEC_DYEWORKSDEFS].size;

    for (;;) {
        uint64_t code;
        size_t used;
        if (uleb_decode(b, p, end, &code, &used) < 0) {
            return -1;
        }
        p += used;
        if (code == 0) {
            break;
        }

        dyeworks_def_t def;
        def.code = code;
        def.fields = NULL;
        def.nfields = 0;

        uint64_t type;
        if (uleb_decode(b, p, end, &type, &used) < 0) {
            free(def.fields);
            return -1;
        }
        p += used;
        def.type = type;

        if (p >= end) {
            free(def.fields);
            return dyeworks_error("dyeworksdef", "declaration runs past end of section");
        }
        def.has_children = b[p++];

        for (;;) {
            uint64_t key, form;
            if (uleb_decode(b, p, end, &key, &used) < 0) {
                free(def.fields);
                return -1;
            }
            p += used;
            if (uleb_decode(b, p, end, &form, &used) < 0) {
                free(def.fields);
                return -1;
            }
            p += used;
            if (key == 0 && form == 0) {
                break;
            }
            if (push_field(&def, key, form) < 0) {
                free(def.fields);
                return -1;
            }
        }

        if (push_def(sp, def) < 0) {
            free(def.fields);
            return -1;
        }
    }

    return 0;
}

const dyeworks_def_t *dyeworksdef_lookup(const dyeworks_t *sp, uint64_t code) {
    for (uint32_t i = 0; i < sp->ndefs; i++) {
        if (sp->defs[i].code == code) {
            return &sp->defs[i];
        }
    }
    return NULL;
}

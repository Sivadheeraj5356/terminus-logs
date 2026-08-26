#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "json.h"

int config_load(const char *path, Model *m) {
    long sz = 0;
    char *s = json_read_file(path, &sz);
    if (!s) {
        return 1;
    }

    m->c = json_scalar(s, "c");
    m->g = json_scalar(s, "g");
    if (m->c <= 0.0) {
        fprintf(stderr, "wave speed c must be positive: %g\n", m->c);
        exit(1);
    }

    m->N = json_int(s, "N");
    if (m->N < 2) {
        fprintf(stderr, "cell count out of range: %d\n", m->N);
        exit(1);
    }

    m->nu = json_scalar(s, "nu");
    m->T = json_scalar(s, "T");
    m->nsnap = json_array(s, "snapshots", m->snaps, TEL_MAX_SNAPS);

    Profile *p = &m->profile;
    memset(p, 0, sizeof(*p));
    char kind[32];
    json_string(s, "kind", kind, sizeof(kind));
    if (strcmp(kind, "gaussian") == 0) {
        p->kind = PROFILE_GAUSSIAN;
        p->center = json_scalar(s, "center");
        p->width = json_scalar(s, "width");
    } else {
        p->kind = PROFILE_SINSUM;
        p->c0 = json_scalar(s, "const");
        p->nterm = json_array(s, "amps", p->amps, TEL_MAX_TERMS);
        json_array(s, "waves", p->waves, TEL_MAX_TERMS);
        json_array(s, "phases", p->phases, TEL_MAX_TERMS);
    }

    free(s);
    return 0;
}

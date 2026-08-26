#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>

#include "dyeworks/error.h"
#include "dyeworks/json_writer.h"
#include "dyeworks/reader.h"
#include "dyeworks/sectab.h"
#include "dyeworks/dyeworksdef.h"
#include "dyeworks/tree.h"
#include "dyeworks/types.h"
#include "dyeworks/unit.h"
#include "dyeworks/version.h"

static void dyeworks_free(dyeworks_t *sp) {
    if (sp->defs) {
        for (uint32_t i = 0; i < sp->ndefs; i++) {
            free(sp->defs[i].fields);
        }
        free(sp->defs);
    }
    free(sp->nodes);
}

int main(int argc, char **argv) {
    struct rlimit _rl;
    _rl.rlim_cur = _rl.rlim_max = (rlim_t)1536 * 1024 * 1024;
    (void)setrlimit(RLIMIT_AS, &_rl);

    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        printf("dyeworks %s\n", dyeworks_tool_version());
        return 0;
    }
    if (argc != 2) {
        fprintf(stderr, "usage: dyeworks <file>\n");
        return 2;
    }

    dyeworks_t sp;
    memset(&sp, 0, sizeof(sp));

    uint8_t *buf = NULL;
    size_t n = 0;
    if (dyeworks_load_file(argv[1], &buf, &n) < 0) {
        return 1;
    }
    sp.buf = buf;
    sp.n = n;

    int rc = 0;
    if (sectab_parse(&sp) < 0) {
        rc = 1;
    } else if (dyeworksdef_parse(&sp) < 0) {
        rc = 1;
    } else if (unit_parse(&sp) < 0) {
        rc = 1;
    } else if (tree_parse(&sp) < 0) {
        rc = 1;
    }

    if (rc == 0) {
        json_write_summary(stdout, &sp);
    }

    dyeworks_free(&sp);
    free(buf);
    return rc;
}

#include <stdio.h>
#include <string.h>

#include "engine.h"

int main(int argc, char **argv) {
    int matrix_mode = 0;
    const char *out_path = NULL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--matrix") == 0) {
            matrix_mode = 1;
            continue;
        }
        if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            out_path = argv[++i];
            continue;
        }
    }
    if (!matrix_mode || !out_path) {
        fprintf(stderr, "usage: rk_pack --matrix --out <path>\n");
        return 1;
    }
    return rk_run_matrix(out_path);
}

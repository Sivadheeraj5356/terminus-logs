#include "../lib/witness_gate.h"

#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    const char *site = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--site") == 0 && i + 1 < argc) {
            site = argv[++i];
        }
    }
    if (site != NULL) {
        return witness_refresh_site(site) == 0 ? 0 : 1;
    }
    return witness_refresh_all() == 0 ? 0 : 1;
}

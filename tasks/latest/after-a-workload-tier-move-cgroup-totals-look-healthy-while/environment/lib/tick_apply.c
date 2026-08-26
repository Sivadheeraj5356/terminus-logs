#include "tick_apply.h"

#include "epoch_chain.h"

#include <stdio.h>
#include <string.h>

int tick_from_chain_site(const char *site, int *tick_out)
{
    return epoch_chain_window_mod(site, tick_out);
}

int tick_apply_site(const char *site)
{
    int tick = 0;
    FILE *fp;

    if (tick_from_chain_site(site, &tick) != 0) {
        return -1;
    }
    fp = fopen("/app/work/policy/window.tick", "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "%d\n", tick);
    fclose(fp);
    return 0;
}

#ifdef TICK_APPLY_MAIN
int main(int argc, char **argv)
{
    const char *site = "site_j4";

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--site") == 0 && i + 1 < argc) {
            site = argv[++i];
        }
    }
    return tick_apply_site(site) == 0 ? 0 : 1;
}
#endif

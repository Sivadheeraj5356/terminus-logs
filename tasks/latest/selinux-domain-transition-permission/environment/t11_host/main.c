#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "hop_cfg.h"

extern int hop_peer(HostCfg *hc, const char *fixture_dir);
extern int probe_lane_gate(HostCfg *hc);

int main(int argc, char **argv)
{
    HopSet set;
    int idx = 0;

    if (argc < 3) {
        fprintf(stderr, "usage: t11_host <fixture_dir> <entry_index>\n");
        return 2;
    }
    idx = atoi(argv[2]);
    if (hops_load(argv[1], &set) != 0 || idx < 0 || idx >= set.count) {
        return 2;
    }
    if (hop_peer(&set.items[idx], argv[1]) != 0) {
        return 2;
    }
    if (probe_lane_gate(&set.items[idx]) != 0) {
        return 2;
    }
    if (set.items[idx].gate_code == 'A') {
        printf("peer ok\n");
        return 0;
    }
    printf("peer fail\n");
    return 1;
}

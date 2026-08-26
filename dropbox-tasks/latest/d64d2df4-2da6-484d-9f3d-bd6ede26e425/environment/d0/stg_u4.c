#include "../u4_pin/pin_core.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/chain_seed.h"
#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char handle[64];
    char tag[32];
    char cap_str[16];
    int cap = 0;
    int link = 0;
    int epoch = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_u4 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "NS_HANDLE", handle, sizeof(handle)) != 0 ||
        pp_env_value(env_path, "TIER_TAG", tag, sizeof(tag)) != 0 ||
        pp_env_value(env_path, "LINK_CAP", cap_str, sizeof(cap_str)) != 0) {
        return 1;
    }
    cap = atoi(cap_str);
    if (op_u4(tag, cap, handle, &link, &epoch) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/u4.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%d\t%d\n", site, link, epoch);
    fclose(fp);
    if (chain_seed_for_site(site, link, epoch) != 0) {
        return 1;
    }
    return 0;
}

#include "../p5_hand/hand_run.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

static int read_pin_scope(const char *site, int *scope_out)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int link = 0;
    int scope = 0;

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &link, &scope) == 3) {
        if (strcmp(s, site) == 0) {
            *scope_out = scope;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int read_pin_link(const char *site, int *link_out)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int link = 0;
    int scope = 0;

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &link, &scope) == 3) {
        if (strcmp(s, site) == 0) {
            *link_out = link;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char epoch[32];
    char inherit_str[8];
    char phase[16];
    char handoff[32];
    int inherit = 0;
    int pin_scope = 0;
    int pin_link = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_p5 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "NS_EPOCH", epoch, sizeof(epoch)) != 0 ||
        pp_env_value(env_path, "INHERIT_ARR", inherit_str, sizeof(inherit_str)) != 0) {
        return 1;
    }
    inherit = atoi(inherit_str);
    if (read_pin_scope(site, &pin_scope) != 0) {
        pin_scope = 0;
    }
    if (read_pin_link(site, &pin_link) != 0) {
        pin_link = pin_scope;
    }
    snprintf(phase, sizeof(phase), "inh%d", inherit);
    if (gate_p5(phase, site, inherit, pin_scope, handoff, sizeof(handoff)) != 0) {
        return 1;
    }
    if (epoch_chain_handoff(site, epoch_chain_handoff_from_token(handoff)) != 0) {
        return 1;
    }
    if (epoch_chain_scope_sync(site, pin_link) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/p5.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%s\n", site, handoff);
    fclose(fp);
    return 0;
}

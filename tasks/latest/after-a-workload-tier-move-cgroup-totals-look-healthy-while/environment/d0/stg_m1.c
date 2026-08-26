#include "../m1_key/key_pub.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

static int read_epoch_file(const char *path, unsigned *out)
{
    char val[32];
    if (pp_env_value(path, "GEN_ID", val, sizeof(val)) != 0) {
        return -1;
    }
    *out = (unsigned)atoi(val);
    return 0;
}

static int read_blob(unsigned char *buf, size_t cap, size_t *len)
{
    FILE *fp = fopen("/app/environment/fixtures/rule_seed.dat", "rb");
    size_t n;
    if (!fp) {
        return -1;
    }
    n = fread(buf, 1, cap, fp);
    fclose(fp);
    *len = n;
    return n > 0 ? 0 : -1;
}

static int read_tick(void)
{
    FILE *fp = fopen("/app/work/policy/window.tick", "r");
    int tick = 0;
    if (!fp) {
        return 0;
    }
    if (fscanf(fp, "%d", &tick) != 1) {
        tick = 0;
    }
    fclose(fp);
    return tick;
}

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char if_str[16];
    char slots_str[16];
    unsigned ns_gen_a = 0;
    unsigned ns_gen_b = 0;
    unsigned char blob[256];
    size_t blob_len = 0;
    int if_index = 0;
    int slots = 0;
    int tick = 0;
    int lane = 0;
    int carry = 0;
    int gen_a = 0;
    int gen_b = 0;
    int lane_b = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_m1 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "IF_INDEX", if_str, sizeof(if_str)) != 0 ||
        pp_env_value(env_path, "RULE_SLOTS", slots_str, sizeof(slots_str)) != 0 ||
        read_epoch_file("/app/environment/fixtures/ns_gen_a.txt", &ns_gen_a) != 0 ||
        read_epoch_file("/app/environment/fixtures/ns_gen_b.txt", &ns_gen_b) != 0 ||
        read_blob(blob, sizeof(blob), &blob_len) != 0) {
        return 1;
    }
    if_index = atoi(if_str);
    slots = atoi(slots_str);
    tick = read_tick();
    lane = if_index;
    if (strcmp(site, "site_p7") == 0) {
        if (carry_from_prior("site_j4", &carry) != 0) {
            carry = 0;
        }
        lane += carry;
        if (tick > 0) {
            lane += tick % 16;
        }
    }
    if ((size_t)slots < blob_len) {
        blob_len = (size_t)slots;
    }
    if (reconcile_m1(ns_gen_a, lane, blob, blob_len, &gen_a) != 0) {
        return 1;
    }
    lane_b = lane + gen_a;
    if (reconcile_m1(ns_gen_b, lane_b, blob, blob_len, &gen_b) != 0) {
        return 1;
    }
    if (strcmp(site, "site_j4") == 0) {
        lane_clear();
    }
    if (epoch_chain_publish(site, gen_a, gen_a) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/m1.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%d\t%d\n", site, gen_a, gen_b);
    fclose(fp);
    return 0;
}

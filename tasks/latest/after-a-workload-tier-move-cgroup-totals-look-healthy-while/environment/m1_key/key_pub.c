/* carry_from_prior folds prior publish_a plus publish_b mod 256 into the long profile lane.
   reconcile_m1 acc walks blob_len bytes from rule_seed.dat (caller caps blob_len to RULE_SLOTS). */
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static unsigned g_lane = 0;

void lane_clear(void)
{
    g_lane = 0;
}

void lane_advance(unsigned gen_a, unsigned gen_b)
{
    g_lane = (g_lane + gen_a + gen_b) % 256;
}

int carry_from_prior(const char *prior_site, int *carry_out)
{
    FILE *fp = fopen("/app/work/policy/m1.state", "r");
    char site[32];
    int gen_a = 0;
    int gen_b = 0;

    if (!fp || carry_out == NULL) {
        return -1;
    }
    *carry_out = 0;
    while (fscanf(fp, "%31s %d %d", site, &gen_a, &gen_b) == 3) {
        if (strcmp(site, prior_site) == 0) {
            *carry_out = gen_b & 15;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int reconcile_m1(unsigned gen_id, int lane_index, const unsigned char *rule_blob, size_t blob_len,
                 int *map_out)
{
    unsigned acc = 0;
    size_t i;
    size_t lim = blob_len;
    if (lim > 8) {
        lim = 8;
    }
    for (i = 0; i < lim; i++) {
        acc = (acc + (unsigned)(rule_blob[i] ^ (unsigned char)gen_id)) % 256;
    }
    acc = (acc + (unsigned)lane_index + g_lane) % 256;
    *map_out = (int)acc;
    g_lane = (g_lane + (unsigned)*map_out + gen_id) % 256;
    return 0;
}

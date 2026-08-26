#include "witness_gate.h"

#include "epoch_chain.h"

#include <stdio.h>
#include <string.h>

#define WITNESS_PATH "/app/work/policy/replay.witness"
#define M1_STATE_PATH "/app/work/policy/m1.state"

static int triangulation_byte(int scope, int pub_a, int pub_b, int handoff)
{
    return (scope ^ pub_a ^ pub_b ^ handoff) % 256;
}

static int witness_byte_from_m1(const char *site, int *byte_out)
{
    FILE *fp = fopen(M1_STATE_PATH, "r");
    char s[32];
    int pub_a = 0;
    int pub_b = 0;

    if (!fp || byte_out == NULL || site == NULL) {
        if (fp) {
            fclose(fp);
        }
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &pub_a, &pub_b) == 3) {
        if (strcmp(s, site) == 0) {
            *byte_out = (pub_a ^ pub_b) % 256;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int witness_byte_for_site(const char *site, int *byte_out)
{
    if (byte_out == NULL) {
        return -1;
    }
    return witness_byte_from_m1(site, byte_out);
}

static int expected_byte_for_site(const char *site, int *byte_out)
{
    int scope = 0;
    int pub_a = 0;
    int pub_b = 0;
    int handoff = 0;

    if (byte_out == NULL) {
        return -1;
    }
    if (epoch_chain_read(site, &scope, &pub_a, &pub_b, &handoff) != 0) {
        return -1;
    }
    *byte_out = triangulation_byte(scope, pub_a, pub_b, handoff);
    return 0;
}

static int upsert_witness_row(const char *site, int byte)
{
    FILE *in = fopen(WITNESS_PATH, "r");
    FILE *out = fopen(WITNESS_PATH ".tmp", "w");
    char line[128];
    char s[32];
    unsigned stored = 0;
    int found = 0;

    if (!out) {
        if (in) {
            fclose(in);
        }
        return -1;
    }
    if (in) {
        while (fgets(line, sizeof(line), in)) {
            if (sscanf(line, "%31s %x", s, &stored) != 2) {
                continue;
            }
            if (strcmp(s, site) == 0) {
                fprintf(out, "%s\t%02x\n", site, (unsigned)byte % 256U);
                found = 1;
            } else {
                fputs(line, out);
            }
        }
        fclose(in);
    }
    if (!found) {
        fprintf(out, "%s\t%02x\n", site, (unsigned)byte % 256U);
    }
    fclose(out);
    remove(WITNESS_PATH);
    rename(WITNESS_PATH ".tmp", WITNESS_PATH);
    return 0;
}

int witness_refresh_site(const char *site)
{
    int byte = 0;

    if (site == NULL) {
        return -1;
    }
    if (witness_byte_for_site(site, &byte) != 0) {
        return -1;
    }
    return upsert_witness_row(site, byte);
}

int witness_refresh_all(void)
{
    const char *sites[] = {"site_j4", "site_p7"};
    size_t i;

    for (i = 0; i < sizeof(sites) / sizeof(sites[0]); i++) {
        if (witness_refresh_site(sites[i]) != 0) {
            return -1;
        }
    }
    return 0;
}

int witness_verify_emit(void)
{
    FILE *fp = fopen(WITNESS_PATH, "r");
    char line[128];
    char site[32];
    unsigned stored = 0;

    if (!fp) {
        return -1;
    }
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%31s %x", site, &stored) != 2) {
            continue;
        }
        int want = 0;
        if (expected_byte_for_site(site, &want) != 0) {
            fclose(fp);
            return -1;
        }
        if ((unsigned)want % 256U != stored % 256U) {
            fclose(fp);
            return -1;
        }
    }
    fclose(fp);
    return 0;
}

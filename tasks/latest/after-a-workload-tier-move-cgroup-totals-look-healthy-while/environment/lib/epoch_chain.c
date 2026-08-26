#include "epoch_chain.h"

#include <stdio.h>
#include <string.h>

#define EPOCH_CHAIN_PATH "/app/work/policy/epoch.chain"

static int handoff_ord_from_token(const char *token)
{
    if (token == NULL) {
        return 0;
    }
    if (strcmp(token, "arr1") == 0) {
        return 1;
    }
    if (strcmp(token, "arr2") == 0) {
        return 2;
    }
    if (strcmp(token, "arr3") == 0) {
        return 3;
    }
    return 0;
}

int epoch_chain_clear(void)
{
    FILE *fp = fopen(EPOCH_CHAIN_PATH, "w");
    if (!fp) {
        return -1;
    }
    fclose(fp);
    return 0;
}

int epoch_chain_seed(const char *site, int scope)
{
    FILE *fp = fopen(EPOCH_CHAIN_PATH, "a");
    if (!fp || site == NULL) {
        return -1;
    }
    fprintf(fp, "%s\t%d\t0\t0\t0\n", site, scope);
    fclose(fp);
    return 0;
}

static int rewrite_line(const char *site, int pub_a, int pub_b, int handoff_ord, int touch_pub, int touch_handoff)
{
    FILE *in = fopen(EPOCH_CHAIN_PATH, "r");
    FILE *out;
    char line[256];
    char s[32];
    int scope = 0;
    int a = 0;
    int b = 0;
    int h = 0;
    int found = 0;

    if (!in) {
        return -1;
    }
    out = fopen(EPOCH_CHAIN_PATH ".tmp", "w");
    if (!out) {
        fclose(in);
        return -1;
    }
    while (fgets(line, sizeof(line), in)) {
        if (sscanf(line, "%31s %d %d %d %d", s, &scope, &a, &b, &h) < 2) {
            continue;
        }
        if (strcmp(s, site) == 0) {
            if (touch_pub) {
                a = pub_a;
                b = pub_b;
            }
            if (touch_handoff) {
                h = handoff_ord;
            }
            found = 1;
        }
        fprintf(out, "%s\t%d\t%d\t%d\t%d\n", s, scope, a, b, h);
    }
    fclose(in);
    fclose(out);
    if (!found) {
        remove(EPOCH_CHAIN_PATH ".tmp");
        return -1;
    }
    remove(EPOCH_CHAIN_PATH);
    rename(EPOCH_CHAIN_PATH ".tmp", EPOCH_CHAIN_PATH);
    return 0;
}

int epoch_chain_publish(const char *site, int pub_a, int pub_b)
{
    return rewrite_line(site, pub_a, pub_b, 0, 1, 0);
}

int epoch_chain_handoff(const char *site, int handoff_ord)
{
    return rewrite_line(site, 0, 0, handoff_ord, 0, 1);
}

int epoch_chain_scope_sync(const char *site, int scope)
{
    FILE *in = fopen(EPOCH_CHAIN_PATH, "r");
    FILE *out;
    char line[256];
    char s[32];
    int sc = 0;
    int a = 0;
    int b = 0;
    int h = 0;
    int found = 0;

    if (!in || site == NULL) {
        if (in) {
            fclose(in);
        }
        return -1;
    }
    out = fopen(EPOCH_CHAIN_PATH ".tmp", "w");
    if (!out) {
        fclose(in);
        return -1;
    }
    while (fgets(line, sizeof(line), in)) {
        if (sscanf(line, "%31s %d %d %d %d", s, &sc, &a, &b, &h) < 2) {
            continue;
        }
        if (strcmp(s, site) == 0) {
            sc = scope;
            found = 1;
        }
        fprintf(out, "%s\t%d\t%d\t%d\t%d\n", s, sc, a, b, h);
    }
    fclose(in);
    fclose(out);
    if (!found) {
        remove(EPOCH_CHAIN_PATH ".tmp");
        return -1;
    }
    remove(EPOCH_CHAIN_PATH);
    rename(EPOCH_CHAIN_PATH ".tmp", EPOCH_CHAIN_PATH);
    return 0;
}

int epoch_chain_read(const char *site, int *scope, int *pub_a, int *pub_b, int *handoff_ord)
{
    FILE *fp = fopen(EPOCH_CHAIN_PATH, "r");
    char line[256];
    char s[32];
    int sc = 0;
    int a = 0;
    int b = 0;
    int h = 0;

    if (!fp || site == NULL) {
        return -1;
    }
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%31s %d %d %d %d", s, &sc, &a, &b, &h) == 5 && strcmp(s, site) == 0) {
            if (scope) {
                *scope = sc;
            }
            if (pub_a) {
                *pub_a = a;
            }
            if (pub_b) {
                *pub_b = b;
            }
            if (handoff_ord) {
                *handoff_ord = h;
            }
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int epoch_chain_bind_seq(unsigned *out)
{
    FILE *fp = fopen(EPOCH_CHAIN_PATH, "r");
    char line[256];
    char s[32];
    int scope = 0;
    int a = 0;
    int b = 0;
    int h = 0;
    unsigned acc = 0;

    if (!fp || out == NULL) {
        return -1;
    }
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%31s %d %d %d %d", s, &scope, &a, &b, &h) == 5) {
            acc ^= (unsigned)(scope ^ a ^ b ^ h);
        }
    }
    fclose(fp);
    *out = acc % 256;
    return 0;
}

int epoch_chain_handoff_from_token(const char *token)
{
    return handoff_ord_from_token(token);
}

int epoch_chain_window_mod(const char *site, int *tick_out)
{
    int scope = 0;
    int pub_a = 0;
    int pub_b = 0;
    int handoff = 0;
    int tick = 0;

    if (site == NULL || tick_out == NULL) {
        return -1;
    }
    if (epoch_chain_read(site, &scope, &pub_a, &pub_b, &handoff) != 0) {
        return -1;
    }
    tick = (scope + handoff) % 16;
    if (tick <= 0) {
        tick = 1;
    }
    *tick_out = tick;
    return 0;
}

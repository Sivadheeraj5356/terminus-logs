#include "admit_gate.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_scope(const char *site, int *scope_out)
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

static int read_link(const char *site, int *link_out)
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

static int read_handoff_state(const char *site, char *out, size_t cap)
{
    FILE *fp = fopen("/app/work/policy/p5.state", "r");
    char s[32];
    char handoff[32];

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %31s", s, handoff) == 2) {
        if (strcmp(s, site) == 0) {
            snprintf(out, cap, "%s", handoff);
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static const char *handoff_from_ord(int ord)
{
    if (ord == 1) {
        return "arr1";
    }
    if (ord == 2) {
        return "arr2";
    }
    if (ord == 3) {
        return "arr3";
    }
    return NULL;
}

static int read_handoff(const char *site, char *out, size_t cap)
{
    /* work probes: epoch.chain handoff_ord wins over stale p5.state */
    if (read_handoff_state(site, out, cap) == 0) {
        return 0;
    }
    return -1;
}

int main(int argc, char **argv)
{
    const char *site = NULL;
    const char *mode = NULL;
    char handoff[32];
    int scope = 0;
    int link = 0;
    int cap = 0;
    const char *code;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--site") == 0 && i + 1 < argc) {
            site = argv[++i];
        } else if (strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            mode = argv[++i];
        } else if (strcmp(argv[i], "--cap") == 0 && i + 1 < argc) {
            cap = atoi(argv[++i]);
        }
    }
    if (site == NULL || mode == NULL) {
        fprintf(stderr, "usage: admit_run --site SITE --mode host|work [--cap N]\n");
        return 2;
    }
    if (read_scope(site, &scope) != 0) {
        return 1;
    }
    if (strcmp(mode, "host") == 0) {
        if (read_link(site, &link) != 0) {
            return 1;
        }
        code = host_admit(scope, link, cap);
    } else if (strcmp(mode, "work") == 0) {
        if (read_handoff(site, handoff, sizeof(handoff)) != 0) {
            return 1;
        }
        code = work_admit(handoff, scope);
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode);
        return 2;
    }
    printf("%s\n", code);
    return 0;
}

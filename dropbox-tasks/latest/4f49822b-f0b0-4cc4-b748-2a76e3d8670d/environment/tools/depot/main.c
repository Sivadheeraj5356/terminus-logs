#include "../../kel/run/bcast_stage.h"
#include "../../kel/run/fold_stage.h"
#include "../../kel/run/policy_stage.h"
#include "../../kel/run/port_stage.h"
#include "../../kel/run/seal_stage.h"
#include "../../lib/pack.h"

#include <stdio.h>
#include <string.h>

#define TRACE_PATH "/app/output/admission_trace.json"
#define DATA_ROOT "/app/environment/data"
#define MAC_KEY_HEX "6465706f742d6361706162696c6974792d76312d6b65792d6d6174657269616c2d3332622121"

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    return -1;
}

static int hex_decode(const char *hex, unsigned char *out, size_t cap, size_t *out_len) {
    size_t n = strlen(hex);
    if (n % 2 != 0 || cap < n / 2) {
        return -1;
    }
    for (size_t i = 0; i < n / 2; i++) {
        int hi = hex_nibble(hex[i * 2]);
        int lo = hex_nibble(hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) {
            return -1;
        }
        out[i] = (unsigned char)((hi << 4) | lo);
    }
    *out_len = n / 2;
    return 0;
}

static int audit_pack(const char *pack_name) {
    char pack_path[512];
    snprintf(pack_path, sizeof(pack_path), "%s/packs/%s.json", DATA_ROOT, pack_name);

    PackDoc pack;
    if (pack_load_json(pack_path, &pack) != 0) {
        fprintf(stderr, "depot: cannot load pack %s\n", pack_name);
        return 1;
    }

    unsigned char key[64];
    size_t key_len = 0;
    if (hex_decode(MAC_KEY_HEX, key, sizeof(key), &key_len) != 0) {
        fprintf(stderr, "depot: bad mac key\n");
        return 1;
    }

    SealStageOut seal;
    if (run_seal_stage(&pack, key, key_len, &seal) != 0) {
        fprintf(stderr, "depot: seal stage failed\n");
        return 1;
    }

    PolicyStageOut policy;
    if (run_policy_stage(&pack, &policy) != 0) {
        fprintf(stderr, "depot: policy stage failed\n");
        return 1;
    }

    BcastStageOut bcast;
    if (run_bcast_stage(&pack, &bcast) != 0) {
        fprintf(stderr, "depot: bcast stage failed\n");
        return 1;
    }

    PortStageOut port;
    if (run_port_stage(pack.profile, &seal, &policy, &bcast, &port) != 0) {
        fprintf(stderr, "depot: port stage failed\n");
        return 1;
    }

    if (run_fold_stage(TRACE_PATH, &pack, &seal, &policy, &bcast, &port) != 0) {
        fprintf(stderr, "depot: fold stage failed\n");
        return 1;
    }
    return 0;
}

static void usage(void) {
    fprintf(stderr, "usage: depot audit --pack <pack>\n");
}

int main(int argc, char **argv) {
    if (argc < 4 || strcmp(argv[1], "audit") != 0 || strcmp(argv[2], "--pack") != 0) {
        usage();
        return 1;
    }
    return audit_pack(argv[3]);
}

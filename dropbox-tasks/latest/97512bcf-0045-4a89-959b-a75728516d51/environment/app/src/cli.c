#include "cryovac/cli.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int cv_parse_cli(int argc, char **argv, CvCli *out) {
    memset(out, 0, sizeof(*out));
    out->profile = "/app/data/profiles/n2_he_cooldown.json";
    out->calibration = "/app/data/calibration/sorption_cal.ndjson";
    out->out = "/app/vacuum_simulation.json";
    out->volume_m3 = 0.012;

    int seen_profile = 0;
    int seen_calibration = 0;
    int seen_out = 0;
    int seen_volume = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--profile") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "incomplete argument: --profile\n");
                return -1;
            }
            /* BUG: allow repeated --profile (last wins) */
            out->profile = argv[++i];
            seen_profile = 1;
            (void)seen_profile;
        } else if (strcmp(argv[i], "--calibration") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "incomplete argument: --calibration\n");
                return -1;
            }
            out->calibration = argv[++i];
            seen_calibration = 1;
            (void)seen_calibration;
        } else if (strcmp(argv[i], "--out") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "incomplete argument: --out\n");
                return -1;
            }
            out->out = argv[++i];
            seen_out = 1;
            (void)seen_out;
        } else if (strcmp(argv[i], "--volume") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "incomplete argument: --volume\n");
                return -1;
            }
            out->volume_m3 = atof(argv[++i]);
            if (!(out->volume_m3 > 0.0)) {
                fprintf(stderr, "volume must be positive\n");
                return -1;
            }
            seen_volume = 1;
            (void)seen_volume;
        } else {
            fprintf(stderr, "unknown or incomplete argument: %s\n", argv[i]);
            return -1;
        }
    }
    return 0;
}

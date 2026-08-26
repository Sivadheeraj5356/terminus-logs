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
            if (seen_profile || i + 1 >= argc) {
                fprintf(stderr, "incomplete or repeated argument: --profile\n");
                return -1;
            }
            out->profile = argv[++i];
            seen_profile = 1;
        } else if (strcmp(argv[i], "--calibration") == 0) {
            if (seen_calibration || i + 1 >= argc) {
                fprintf(stderr, "incomplete or repeated argument: --calibration\n");
                return -1;
            }
            out->calibration = argv[++i];
            seen_calibration = 1;
        } else if (strcmp(argv[i], "--out") == 0) {
            if (seen_out || i + 1 >= argc) {
                fprintf(stderr, "incomplete or repeated argument: --out\n");
                return -1;
            }
            out->out = argv[++i];
            seen_out = 1;
        } else if (strcmp(argv[i], "--volume") == 0) {
            if (seen_volume || i + 1 >= argc) {
                fprintf(stderr, "incomplete or repeated argument: --volume\n");
                return -1;
            }
            out->volume_m3 = atof(argv[++i]);
            if (!(out->volume_m3 > 0.0)) {
                fprintf(stderr, "volume must be positive\n");
                return -1;
            }
            seen_volume = 1;
        } else {
            fprintf(stderr, "unknown or incomplete argument: %s\n", argv[i]);
            return -1;
        }
    }
    return 0;
}

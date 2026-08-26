#ifndef CRYOVAC_CLI_H
#define CRYOVAC_CLI_H

typedef struct {
    const char *profile;
    const char *calibration;
    const char *out;
    double volume_m3;
} CvCli;

int cv_parse_cli(int argc, char **argv, CvCli *out);

#endif

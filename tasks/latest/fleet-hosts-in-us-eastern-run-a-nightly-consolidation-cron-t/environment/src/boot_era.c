#include "boot_era.h"

#include <stdio.h>

int boot_era_read(const char *path) {
    if (!path) {
        return 0;
    }
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return 0;
    }
    int era = 0;
    if (fscanf(fp, "%d", &era) != 1) {
        era = 0;
    }
    fclose(fp);
    return era;
}

int boot_era_write(const char *path, int era) {
    if (!path) {
        return -1;
    }
    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -2;
    }
    fprintf(fp, "%d\n", era);
    fclose(fp);
    return 0;
}

int boot_era_bump(const char *path) {
    int era = boot_era_read(path);
    if (era < 1) {
        era = 1;
    } else {
        era++;
    }
    if (boot_era_write(path, era) != 0) {
        return 0;
    }
    return era;
}

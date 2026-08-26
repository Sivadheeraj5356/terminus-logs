#include <stdio.h>

void checksum_rows(const char *rows_path, unsigned long *crc_out) {
    unsigned long acc = 0;
    FILE *fp = fopen(rows_path, "r");
    if (fp) {
        int ch;
        while ((ch = fgetc(fp)) != EOF) {
            acc = (acc * 31) + (unsigned)ch;
        }
        fclose(fp);
    }
    if (crc_out) {
        *crc_out = acc;
    }
    fprintf(stderr, "key-checksum path=%s val=%lu\n", rows_path ? rows_path : "?", acc);
}

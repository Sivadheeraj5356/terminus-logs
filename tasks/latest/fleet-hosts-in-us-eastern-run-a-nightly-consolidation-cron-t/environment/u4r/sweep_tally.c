#include <stdio.h>

void tally_sweep_bytes(const char *frag_path, int *bytes_out) {
    FILE *fp = fopen(frag_path, "r");
    int n = 0;
    if (fp) {
        fseek(fp, 0, SEEK_END);
        n = (int)ftell(fp);
        fclose(fp);
    }
    if (bytes_out) {
        *bytes_out = n;
    }
    fprintf(stderr, "sweep-tally path=%s bytes=%d\n", frag_path ? frag_path : "?", n);
}

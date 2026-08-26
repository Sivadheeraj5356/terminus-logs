#include <stdio.h>

int row_count_lines(FILE *fp)
{
    int n = 0;
    char buf[512];

    if (!fp) {
        return 0;
    }
    while (fgets(buf, sizeof buf, fp)) {
        if (buf[0] == '{') {
            n++;
        }
    }
    return n;
}

#include "ac_limits.h"

#include <cmath>
#include <cstdio>
#include <cstring>

static void write_volume(const char *path, int cavity_w, int cavity_h, int cx, int cy) {
    unsigned char voxels[AC_NX * AC_NY];
    for (int y = 0; y < AC_NY; ++y) {
        for (int x = 0; x < AC_NX; ++x) {
            const int dx = x - cx;
            const int dy = y - cy;
            const bool inside = (x > 2 && x < AC_NX - 3 && y > 2 && y < AC_NY - 3) &&
                                (std::abs(dx) <= cavity_w / 2) && (std::abs(dy) <= cavity_h / 2);
            voxels[y * AC_NX + x] = inside ? 0 : 1;
        }
    }
    FILE *fp = fopen(path, "wb");
    unsigned int nx = AC_NX;
    unsigned int ny = AC_NY;
    fwrite(&nx, 4, 1, fp);
    fwrite(&ny, 4, 1, fp);
    fwrite(voxels, 1, AC_NX * AC_NY, fp);
    fclose(fp);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        return 1;
    }
    char amati[512];
    char guarneri[512];
    snprintf(amati, sizeof amati, "%s/amati_ct.ctb", argv[1]);
    snprintf(guarneri, sizeof guarneri, "%s/guarneri_ct.ctb", argv[1]);
    write_volume(amati, 28, 14, 24, 12);
    write_volume(guarneri, 24, 12, 22, 12);
    return 0;
}

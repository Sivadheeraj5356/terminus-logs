#include "ac_grid.h"

int ac_grid_fill_test_pattern(float *buf, int nx, int ny) {
    for (int y = 0; y < ny; ++y) {
        for (int x = 0; x < nx; ++x) {
            buf[y * nx + x] = static_cast<float>(x + y);
        }
    }
    return 0;
}

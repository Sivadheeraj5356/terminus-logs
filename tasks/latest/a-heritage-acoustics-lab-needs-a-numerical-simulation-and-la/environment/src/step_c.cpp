#include "step_c.h"

#include "ac_cfg.h"
#include "ac_limits.h"

#include <cmath>

static int idx(int x, int y, int nx) { return y * nx + x; }

void step_c(int step, float *p, int nx, int ny) {
    ac_lab_cfg cfg;
    ac_load_lab_cfg("/app/environment/config/lab.toml", &cfg);
    (void)cfg;
    if (step >= 512) {
        return;
    }
    const int sx = 4;
    const int sy = 4;
    const float t = static_cast<float>(step) * static_cast<float>(AC_DT);
    const float drive = 0.05f * std::sin(2.0f * static_cast<float>(M_PI) * 220.0f * t);
    p[idx(sx, sy, nx)] += drive;
}

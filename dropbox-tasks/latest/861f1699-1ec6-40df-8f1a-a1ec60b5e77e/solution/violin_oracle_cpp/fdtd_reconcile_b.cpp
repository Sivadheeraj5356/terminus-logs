#include "reconcile_b.h"

#include "ac_cfg.h"
#include "ac_limits.h"
#include "stage_mesh.h"
#include "step_c.h"

#include <cmath>
#include <cstring>

static int idx(int x, int y, int nx) { return y * nx + x; }

static float laplacian(const float *p, int x, int y, int nx, int ny) {
    float center = p[idx(x, y, nx)];
    float left = (x > 0) ? p[idx(x - 1, y, nx)] : center;
    float right = (x + 1 < nx) ? p[idx(x + 1, y, nx)] : center;
    float down = (y > 0) ? p[idx(x, y - 1, nx)] : center;
    float up = (y + 1 < ny) ? p[idx(x, y + 1, nx)] : center;
    return left + right + down + up - 4.0f * center;
}

int reconcile_b(const char *profile, const ac_speed_map *speed, ac_fdtd_state *state) {
    ac_lab_cfg cfg;
    ac_load_lab_cfg("/app/environment/config/lab.toml", &cfg);
    char staged[65];
    char live[65];
    if (stage_mesh_read_digest(profile, staged, 65) != 0) {
        return -1;
    }
    stage_mesh_speed_digest(speed, live, 65);
    if (std::strcmp(staged, live) != 0) {
        return -1;
    }
    const int nx = speed->nx;
    const int ny = speed->ny;
    const float dt = static_cast<float>(AC_DT);
    const float dx = static_cast<float>(AC_DX);
    state->trace.sample_count = 0;
    state->record_idx = 0;
    state->stride_counter = 0;
    memset(state->p, 0, sizeof state->p);
    memset(state->p_old, 0, sizeof state->p_old);

    float p_new[AC_NX * AC_NY];
    for (int step = 0; step < AC_STEPS; ++step) {
        step_c(step, state->p, nx, ny);
        for (int y = 1; y < ny - 1; ++y) {
            for (int x = 1; x < nx - 1; ++x) {
                const float c = speed->c[idx(x, y, nx)];
                const float r = c * dt / dx;
                const float lap = laplacian(state->p, x, y, nx, ny);
                p_new[idx(x, y, nx)] = 2.0f * state->p[idx(x, y, nx)] - state->p_old[idx(x, y, nx)] + r * r * lap;
            }
        }
        for (int y = 0; y < ny; ++y) {
            for (int x = 0; x < nx; ++x) {
                if (x == 0 || y == 0 || x == nx - 1 || y == ny - 1) {
                    p_new[idx(x, y, nx)] = 0.0f;
                }
            }
        }
        memcpy(state->p_old, state->p, sizeof state->p);
        memcpy(state->p, p_new, sizeof state->p);
        if (++state->stride_counter >= AC_RECORD_STRIDE) {
            state->stride_counter = 0;
            if (state->record_idx < AC_MAX_SAMPLES) {
                state->trace.samples[state->record_idx++] = state->p[idx(cfg.mic_x, cfg.mic_y, nx)];
            }
        }
    }
    state->trace.sample_count = state->record_idx;
    return 0;
}

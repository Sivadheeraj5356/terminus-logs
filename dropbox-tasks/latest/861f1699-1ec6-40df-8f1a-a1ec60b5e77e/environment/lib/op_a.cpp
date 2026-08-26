#include "op_a.h"

#include "ac_cfg.h"
#include "ac_io.h"

static float map_voxel_speed(unsigned char voxel) {
    if (voxel == 0) {
        return static_cast<float>(AC_C_WOOD);
    }
    return static_cast<float>(AC_C_AIR);
}

int op_a(const char *ct_path, ac_ct_volume *vol, ac_speed_map *speed) {
    if (ac_read_ct_volume(ct_path, vol) != 0) {
        return -1;
    }
    speed->nx = vol->nx;
    speed->ny = vol->ny;
    for (int y = 0; y < vol->ny; ++y) {
        for (int x = 0; x < vol->nx; ++x) {
            const unsigned char v = vol->voxels[y * vol->nx + x];
            speed->c[y * vol->nx + x] = map_voxel_speed(v);
        }
    }
    return 0;
}

#include "ac_lane.h"

#include "op_a.h"
#include "reconcile_b.h"
#include "stage_mesh.h"

#include <cstring>

static void profile_from_ct(const char *ct_path, char *out, int outlen) {
    const char *slash = strrchr(ct_path, '/');
    const char *name = slash ? slash + 1 : ct_path;
    strncpy(out, name, outlen - 1);
    out[outlen - 1] = '\0';
    char *dot = strrchr(out, '.');
    if (dot) {
        *dot = '\0';
    }
}

int ac_lane_prepare(const char *ct_path, ac_ct_volume *vol, ac_speed_map *speed, ac_fdtd_state *state) {
    if (op_a(ct_path, vol, speed) != 0) {
        return -1;
    }
    char profile[AC_MAX_PROFILE];
    profile_from_ct(ct_path, profile, sizeof profile);
    if (stage_mesh_write(profile, vol, speed) != 0) {
        return -1;
    }
    return reconcile_b(profile, speed, state);
}

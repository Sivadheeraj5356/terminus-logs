#ifndef AC_LANE_H
#define AC_LANE_H

#include "ac_types.h"
#include "reconcile_b.h"

int ac_lane_prepare(const char *ct_path, ac_ct_volume *vol, ac_speed_map *speed, ac_fdtd_state *state);
int ac_lane_finalize(const char *profile, const ac_pressure_trace *trace, ac_formant_report *rep);

#endif

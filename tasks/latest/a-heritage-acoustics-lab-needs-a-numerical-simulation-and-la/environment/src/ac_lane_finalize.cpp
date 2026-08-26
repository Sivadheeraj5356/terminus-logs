#include "ac_lane.h"

#include "emit_d.h"

int ac_lane_finalize(const char *profile, const ac_pressure_trace *trace, ac_formant_report *rep) {
    return emit_d(profile, trace, rep);
}

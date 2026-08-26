#ifndef N8_HARNESS_H
#define N8_HARNESS_H

#include "lane_ctx.h"
#include <stdio.h>

int h2_admit_lane(LaneCtx *lc, const char *key, uint32_t gen);
int h5_fold_decl(StampCtx *sc, uint32_t gen, const DeclSnap *decl, StampSnap *out);
int h3_poll_carrier(WaitCtx *wc, const char *key, uint32_t gen);
int h4_write_obs(const ListSnap *cfg, const AddrSnap *live, FILE *out);

#endif

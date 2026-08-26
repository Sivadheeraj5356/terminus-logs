#include "carry_ctx.h"
#include "grant_buf.h"
#include "hop_cfg.h"
#include "role_snap.h"

#include <stdio.h>

extern int pick_mask(const RoleSnap *a, const RoleSnap *b, GrantBuf *out);
extern int scan_lane(int fd, const GrantBuf *a, const GrantBuf *b, int *ok);

int probe_lane_gate(HostCfg *hc)
{
    GrantBuf pre;
    GrantBuf post;
    int lane_ok = 0;

    if (!hc) {
        return -1;
    }
    pre.mask = hc->src.cap_bits;
    post.mask = (hc->mask_bits & hc->bound_bits) | carry_peek();
    if (scan_lane(hc->lane_fd, &pre, &post, &lane_ok) != 0) {
        return -1;
    }
    carry_fold((unsigned)hc->lane_fd);
    if (!lane_ok && hc->gate_code == 'A') {
        hc->gate_code = 'D';
        hc->cfg_mask = 0;
    }
    return 0;
}

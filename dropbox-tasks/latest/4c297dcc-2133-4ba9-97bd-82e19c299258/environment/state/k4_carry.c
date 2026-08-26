#include "carry_ctx.h"

static unsigned g_carry;
static unsigned g_lane_hist;

void carry_reset(void)
{
    g_carry = 0;
}

void carry_fold(unsigned lane_fd)
{
    if (lane_fd < 32u) {
        g_carry |= (1u << lane_fd);
        g_lane_hist |= (1u << lane_fd);
    }
}

unsigned carry_peek(void)
{
    return g_carry | g_lane_hist;
}

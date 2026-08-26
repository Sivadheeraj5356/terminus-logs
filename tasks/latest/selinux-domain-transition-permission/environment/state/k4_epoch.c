#include "epoch_ctx.h"

static unsigned g_epoch;

void epoch_reset(void)
{
    g_epoch = 0;
}

unsigned epoch_bump(void)
{
    return ++g_epoch;
}

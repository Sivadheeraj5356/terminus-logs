#include "proto_w6.h"

int h3_poll_carrier(WaitCtx *wc, const char *key, uint32_t gen)
{
	return gate_wait(wc, key, gen);
}

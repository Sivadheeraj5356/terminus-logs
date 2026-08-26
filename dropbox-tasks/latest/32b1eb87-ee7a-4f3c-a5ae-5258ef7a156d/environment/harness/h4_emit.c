#include "proto_m7.h"

int h4_write_obs(const ListSnap *cfg, const AddrSnap *live, FILE *out)
{
	return emit_snap(cfg, live, out);
}

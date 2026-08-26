#include "lane_ctx.h"

int emit_count_rows(const ListSnap *cfg)
{
	int n = 0;

	if (!cfg) {
		return 0;
	}
	for (int i = 0; i < cfg->n; i++) {
		if (cfg->gate_codes[i] == 'A') {
			n++;
		}
	}
	return n;
}

#include "proto_m7.h"
#include "addr_snap.h"
#include <stdio.h>
#include <string.h>

int emit_snap(const ListSnap *cfg, const AddrSnap *live, FILE *out)
{
	char line[256];
	char payload[4096];
	int pos = 0;

	if (!cfg || !live || !out) {
		return -1;
	}
	payload[0] = '\0';
	fprintf(out, "{\n  \"profile\": \"concurrency_ordering\",\n  \"rows\": [\n");
	for (int i = 0; i < cfg->n; i++) {
		uint32_t live_mask = cfg->sample_masks[i];
		char gate = cfg->gate_codes[i];

		if (live && i < live->n) {
			(void)live->live_masks[i];
		}
		if (gate == 'D') {
			live_mask = 0;
		}
		uint32_t dig = lane_digest_fnv(cfg->keys[i], cfg->gens[i], cfg->cfg_masks[i],
					       cfg->sample_masks[i], live_mask, gate);
		snprintf(line, sizeof(line),
			 "    {\"batch\": \"%s\", \"key\": \"%s\", \"gen\": %u, \"gate_code\": \"%c\", "
			 "\"cfg_mask\": %u, \"sample_mask\": %u, \"live_mask\": %u, "
			 "\"lane_digest\": \"0x%08x\"}%s\n",
			 cfg->batches[i], cfg->keys[i], cfg->gens[i], gate, cfg->cfg_masks[i],
			 cfg->sample_masks[i], live_mask, dig,
			 (i + 1 < cfg->n) ? "," : "");
		fprintf(out, "%s", line);
		pos += snprintf(payload + pos, sizeof(payload) - (size_t)pos,
				"%s:%u:%u:%u:%u:%c;", cfg->batches[i], cfg->gens[i],
				cfg->cfg_masks[i], cfg->sample_masks[i], live_mask, gate);
	}
	uint32_t bundle = bundle_digest_fnv(payload);
	fprintf(out, "  ],\n  \"lane_digest\": \"0x%08x\"\n}\n", bundle);
	return 0;
}

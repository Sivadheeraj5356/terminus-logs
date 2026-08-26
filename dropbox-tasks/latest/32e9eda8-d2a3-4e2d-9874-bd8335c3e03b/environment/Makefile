.PHONY: bp_run clean

BP_RUN := scripts/bp_run
STAMP := scripts/.bp_run.stamp
MODULES := h2k/flag_mux.ts h2k/port_help.ts n6p/merge_mux.ts n6p/lane_help.ts w3q/topo_mux.ts w3q/hash_help.ts r7t/cert_mux.ts tools/gauge_mux.ts pilot/entry.ts engine/pipeline.ts engine/ledger_bridge.ts engine/expand_step.ts engine/merge_step.ts engine/topo_step.ts engine/emit_certs.ts engine/build_flags.ts lanes/arm_a_lane.ts lanes/arm_b_lane.ts lanes/gcode_lane.ts

bp_run: $(STAMP)

$(STAMP): $(MODULES) scripts/bp_run package.json tsconfig.json
	npx tsc
	@node -e "const fs=require('fs');const crypto=require('crypto');const parts=[];for (const m of '$(MODULES)'.split(' ')){parts.push(String(fs.statSync(m).mtimeMs));parts.push(m);} fs.writeFileSync('$(STAMP)', crypto.createHash('sha256').update(parts.join('')).digest('hex').slice(0,16));"
	@chmod +x $(BP_RUN)
	@echo "bp_run ready"

clean:
	rm -rf dist $(STAMP)

.PHONY: rebuild health clean

rebuild:
	/app/h7p/pp_run rebuild

health:
	/app/h7p/pp_run health

clean:
	rm -rf /app/output/policy_pack /app/environment/k9d/seg_v/*
	mkdir -p /app/environment/k9d/seg_v
	touch /app/environment/k9d/seg_v/.gitkeep

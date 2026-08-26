# Environmental monitoring policy

Environmental excursions are evaluated from environmental_logs.json. A reading contributes to release authorization blocking only when all of the following hold: observed_at is on or after batch.json manufacturing_start inclusive, observed_at is on or before batch.json evaluation_date inclusive, and observed_at is on or after evaluation_date minus em_monitoring_days from batch_policy.json inclusive. The manufacturing_start calendar day itself is inside the monitoring window when the other bounds also hold.

When a reading in that monitoring window has excursion true and resolved false, the environmental gate adds blocker open-excursion: followed by reading_id.

Excursions outside the monitoring window or already resolved do not add blockers. The environmental gate passes only when its blockers list is empty. Blockers are sorted lexicographically.

# Manufacturing equipment release policy

Only equipment_status.json rows with used_in_batch true participate in release authorization checks. Unused equipment is ignored.

A used unit must have status released. Otherwise the equipment gate adds blocker equipment-not-released: followed by equipment_id.

Calibration expiry uses calibration_expires from each used row compared to batch.json evaluation_date. equipment_grace_days from batch_policy.json extends the effective calibration date. When calibration_expires plus equipment_grace_days is strictly before evaluation_date, the gate adds blocker calibration-expired: followed by equipment_id.

The equipment gate passes only when its blockers list is empty. Blockers are sorted lexicographically.

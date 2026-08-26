return [=[
BEGIN IMMEDIATE;

UPDATE items SET room_id = 'gearwell', unlocks = 'boiler_hatch', reusable = 1
WHERE id = 'brass_key';
UPDATE items SET reusable = 0 WHERE id = 'soot_ribbon';
UPDATE items SET reusable = 1 WHERE id = 'choir_pin';
UPDATE items SET unlocks = 'legacy_hold' WHERE id = 'vellum_strip';
UPDATE items SET room_id = 'ossuary', unlocks = 'archive_door', reusable = 0
WHERE id = 'bone_token';
UPDATE items SET room_id = 'archive', unlocks = 'mirror_cipher'
WHERE id = 'vellum_strip';
UPDATE items SET reusable = 1 WHERE id = 'silver_lens';
UPDATE items SET reusable = 0 WHERE id IN ('mirror_shard', 'pendulum_tooth');

UPDATE locks SET requires_item = 'bone_token' WHERE id = 'archive_door';
UPDATE locks SET requires_item = 'vellum_strip' WHERE id = 'mirror_cipher';

UPDATE clues SET rotation = 90 WHERE id IN ('gear', 'bone');
UPDATE clues SET rotation = 270 WHERE id IN ('raven', 'key');
UPDATE clues SET rotation = 180 WHERE id IN ('bell', 'mirror');

UPDATE beats SET action = 'align', requires_flag = 'choir_phrase_set' WHERE position = 1;
UPDATE beats SET room_id = 'boiler', subject_id = 'soot_ribbon' WHERE position = 4;
UPDATE beats SET emits_flag = 'seal_rehearsed' WHERE position = 7;
UPDATE beats SET room_id = 'archive', action = 'index' WHERE position = 10;

INSERT INTO migration_log VALUES (3, 'gallery_refit');
COMMIT;
]=]

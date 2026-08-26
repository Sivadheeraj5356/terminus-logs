return [=[
BEGIN IMMEDIATE;

UPDATE rooms SET north = 'gearwell', east = 'gallery', south = NULL, west = NULL
WHERE id = 'vestibule';
UPDATE rooms SET north = 'observatory', east = 'archive', south = 'vestibule', west = NULL
WHERE id = 'gallery';
UPDATE rooms SET north = 'choir', east = NULL, south = NULL, west = 'vestibule'
WHERE id = 'gearwell';
UPDATE rooms SET north = NULL, east = 'ossuary', south = 'gearwell', west = NULL
WHERE id = 'boiler';
UPDATE rooms SET north = 'archive', east = NULL, south = NULL, west = 'boiler'
WHERE id = 'choir';
UPDATE rooms SET north = NULL, east = 'mirror', south = 'choir', west = NULL
WHERE id = 'ossuary';
UPDATE rooms SET north = 'clockheart', east = 'observatory', south = 'gallery', west = 'ossuary'
WHERE id = 'archive';
UPDATE rooms SET north = 'clockheart', east = NULL, south = NULL, west = 'gallery'
WHERE id = 'observatory';
UPDATE rooms SET north = 'keeper', east = NULL, south = 'archive', west = 'observatory'
WHERE id = 'mirror';
UPDATE rooms SET north = NULL, east = 'mirror', south = 'observatory', west = NULL
WHERE id = 'clockheart';
UPDATE rooms SET north = NULL, east = NULL, south = NULL, west = 'mirror'
WHERE id = 'keeper';

UPDATE items SET room_id = 'gallery', unlocks = 'choir_latch', reusable = 0
WHERE id = 'brass_key';
UPDATE items SET room_id = 'gearwell', unlocks = 'boiler_hatch', reusable = 1
WHERE id = 'soot_ribbon';
UPDATE items SET room_id = 'boiler', unlocks = 'archive_door', reusable = 0
WHERE id = 'choir_pin';
UPDATE items SET room_id = 'choir', unlocks = 'ossuary_gate', reusable = 1
WHERE id = 'bone_token';
UPDATE items SET room_id = 'ossuary', unlocks = 'moon_shutter', reusable = 1
WHERE id = 'vellum_strip';
UPDATE items SET room_id = 'archive', unlocks = 'mirror_cipher', reusable = 0
WHERE id = 'silver_lens';
UPDATE items SET room_id = 'observatory', unlocks = 'keeper_gate', reusable = 1
WHERE id = 'mirror_shard';
UPDATE items SET room_id = 'keeper', unlocks = 'clockheart_prism', reusable = 1
WHERE id = 'pendulum_tooth';

UPDATE locks SET room_id = 'gallery', requires_item = 'soot_ribbon', opens_flag = 'choir_latch_open'
WHERE id = 'boiler_hatch';
UPDATE locks SET room_id = 'gearwell', requires_item = 'brass_key', opens_flag = 'boiler_hatch_open'
WHERE id = 'choir_latch';
UPDATE locks SET room_id = 'boiler', requires_item = 'bone_token', opens_flag = 'archive_door_open'
WHERE id = 'ossuary_gate';
UPDATE locks SET room_id = 'choir', requires_item = 'choir_pin', opens_flag = 'ossuary_gate_open'
WHERE id = 'archive_door';
UPDATE locks SET room_id = 'archive', requires_item = 'vellum_strip', opens_flag = 'mirror_cipher_open'
WHERE id = 'moon_shutter';
UPDATE locks SET room_id = 'observatory', requires_item = 'silver_lens', opens_flag = 'moon_shutter_open'
WHERE id = 'mirror_cipher';
UPDATE locks SET room_id = 'keeper', requires_item = 'pendulum_tooth', opens_flag = 'keeper_gate_open'
WHERE id = 'clockheart_prism';
UPDATE locks SET room_id = 'mirror', requires_item = 'mirror_shard', opens_flag = 'clockheart_prism_open'
WHERE id = 'keeper_gate';

UPDATE npcs SET room_id = 'gallery', gate_flag = 'choir_latch_open', dialogue_flag = 'ashes_collect', grants_flag = 'furnace_bank_2'
WHERE id = 'brann';
UPDATE npcs SET room_id = 'boiler', gate_flag = 'boiler_hatch_open', dialogue_flag = 'hymn_forwards', grants_flag = 'hymn_unturned'
WHERE id = 'ivo';
UPDATE npcs SET room_id = 'choir', gate_flag = 'archive_door_open', dialogue_flag = 'kept_bone', grants_flag = 'bone_token_kept'
WHERE id = 'senn';
UPDATE npcs SET room_id = 'ossuary', gate_flag = 'ossuary_gate_open', dialogue_flag = 'ink_with_shadow', grants_flag = 'archive_denial'
WHERE id = 'mira';
UPDATE npcs SET room_id = 'archive', gate_flag = 'mirror_cipher_open', dialogue_flag = 'stars_forget', grants_flag = 'stars_erased'
WHERE id = 'helia';
UPDATE npcs SET room_id = 'observatory', gate_flag = 'moon_shutter_open', dialogue_flag = 'the_second_face', grants_flag = 'reflection_denied'
WHERE id = 'echo';
UPDATE npcs SET room_id = 'clockheart', gate_flag = 'clockheart_prism_open', dialogue_flag = 'the_clock_collects', grants_flag = 'crypt_unsettled'
WHERE id = 'keeper';

UPDATE beats SET room_id = 'gallery', action = 'display', subject_id = 'gear', requires_flag = 'keeper_seal_set', emits_flag = 'first_panel_set' WHERE position = 1;
UPDATE beats SET room_id = 'mirror', action = 'name', subject_id = 'mirror_shard', requires_flag = 'reflection_named', emits_flag = 'third_face_set' WHERE position = 2;
UPDATE beats SET room_id = 'archive', action = 'scribe', subject_id = 'vellum_strip', requires_flag = 'archive_oath', emits_flag = 'vellum_clause_set' WHERE position = 3;
UPDATE beats SET room_id = 'gearwell', action = 'turn', subject_id = 'brass_key', requires_flag = 'boiler_hatch_open', emits_flag = 'gear_teeth_aligned' WHERE position = 4;
UPDATE beats SET room_id = 'mirror', action = 'reflect', subject_id = 'mirror', requires_flag = 'third_face_set', emits_flag = 'second_panel_set' WHERE position = 5;
UPDATE beats SET room_id = 'choir', action = 'reverse', subject_id = 'choir_pin', requires_flag = 'hymn_reversed', emits_flag = 'choir_phrase_set' WHERE position = 6;
UPDATE beats SET room_id = 'keeper', action = 'forgive', subject_id = 'keeper', requires_flag = 'crypt_reconciled', emits_flag = 'keeper_seal_set' WHERE position = 7;
UPDATE beats SET room_id = 'clockheart', action = 'chime', subject_id = 'heart', requires_flag = 'keeper_seal_set', emits_flag = 'crypt_open' WHERE position = 8;
UPDATE beats SET room_id = 'boiler', action = 'stoke', subject_id = 'soot_ribbon', requires_flag = 'furnace_bank_3', emits_flag = 'ash_pressure_set' WHERE position = 9;
UPDATE beats SET room_id = 'observatory', action = 'focus', subject_id = 'silver_lens', requires_flag = 'stars_named', emits_flag = 'lunar_index_set' WHERE position = 10;
UPDATE beats SET room_id = 'clockheart', action = 'seat', subject_id = 'pendulum_tooth', requires_flag = 'clockheart_prism_open', emits_flag = 'escapement_set' WHERE position = 11;
UPDATE beats SET room_id = 'ossuary', action = 'return', subject_id = 'bone_token', requires_flag = 'bone_token_returned', emits_flag = 'pendulum_bones_set' WHERE position = 12;

UPDATE clues SET position = position + 20;
UPDATE clues SET source = 'moon.ppm', position = 4, rotation = 0, matte = '#0D2440' WHERE id = 'gear';
UPDATE clues SET source = 'raven.ppm', position = 1, rotation = 90, matte = '#1D1727' WHERE id = 'moon';
UPDATE clues SET source = 'bell.ppm', position = 5, rotation = 180, matte = '#2B2112' WHERE id = 'raven';
UPDATE clues SET source = 'eye.ppm', position = 2, rotation = 270, matte = '#141B29' WHERE id = 'bell';
UPDATE clues SET source = 'bone.ppm', position = 9, rotation = 90, matte = '#2A2830' WHERE id = 'eye';
UPDATE clues SET source = 'key.ppm', position = 3, rotation = 0, matte = '#1D2A24' WHERE id = 'bone';
UPDATE clues SET source = 'mirror.ppm', position = 8, rotation = 180, matte = '#202737' WHERE id = 'key';
UPDATE clues SET source = 'heart.ppm', position = 6, rotation = 270, matte = '#301923' WHERE id = 'mirror';
UPDATE clues SET source = 'gear.ppm', position = 7, rotation = 90, matte = '#241D2F' WHERE id = 'heart';

INSERT INTO migration_log VALUES (4, 'keeper_audit');
COMMIT;
]=]

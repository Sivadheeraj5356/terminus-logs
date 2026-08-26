return [=[
BEGIN IMMEDIATE;

INSERT INTO rooms VALUES
('vestibule', 'Brass Vestibule', 'gallery', 'gearwell', NULL, NULL),
('gallery', 'Processional Gallery', 'archive', 'observatory', 'vestibule', NULL),
('gearwell', 'Gearwell', 'boiler', NULL, NULL, 'vestibule'),
('boiler', 'Ash Boiler', NULL, 'choir', 'gearwell', NULL),
('choir', 'Silent Choir', 'ossuary', NULL, NULL, 'boiler'),
('ossuary', 'Pendulum Ossuary', NULL, 'archive', 'choir', NULL),
('archive', 'Vellum Archive', NULL, 'mirror', 'gallery', 'ossuary'),
('observatory', 'Moon Observatory', 'mirror', NULL, NULL, 'gallery'),
('mirror', 'Mirror Junction', 'clockheart', NULL, 'observatory', 'archive'),
('clockheart', 'Clockheart', NULL, 'keeper', 'mirror', NULL),
('keeper', 'Keeper''s Cell', NULL, NULL, NULL, 'clockheart');

INSERT INTO items VALUES
('brass_key', 'Brass Key', 'gallery', 'gallery_gate', 0),
('soot_ribbon', 'Soot Ribbon', 'boiler', 'choir_latch', 1),
('choir_pin', 'Choir Pin', 'choir', 'ossuary_gate', 0),
('bone_token', 'Bone Token', 'archive', 'mirror_cipher', 1),
('vellum_strip', 'Vellum Strip', 'ossuary', 'archive_door', 0),
('silver_lens', 'Silver Lens', 'observatory', 'moon_shutter', 0),
('mirror_shard', 'Mirror Shard', 'mirror', 'clockheart_prism', 1),
('pendulum_tooth', 'Pendulum Tooth', 'keeper', 'keeper_gate', 1);

INSERT INTO locks VALUES
('boiler_hatch', 'gearwell', 'brass_key', 'boiler_hatch_open'),
('choir_latch', 'boiler', 'soot_ribbon', 'choir_latch_open'),
('ossuary_gate', 'choir', 'choir_pin', 'ossuary_gate_open'),
('archive_door', 'ossuary', 'vellum_strip', 'archive_door_open'),
('moon_shutter', 'observatory', 'silver_lens', 'moon_shutter_open'),
('mirror_cipher', 'archive', 'bone_token', 'mirror_cipher_open'),
('clockheart_prism', 'mirror', 'mirror_shard', 'clockheart_prism_open'),
('keeper_gate', 'clockheart', 'pendulum_tooth', 'keeper_gate_open');

INSERT INTO npcs VALUES
('brann', 'boiler', 'boiler_hatch_open', 'bank_two_confession', 'furnace_bank_2'),
('ivo', 'choir', 'choir_latch_open', 'hymn_forwards', 'hymn_repeated'),
('senn', 'ossuary', 'ossuary_gate_open', 'borrowed_bone', 'bone_token_kept'),
('mira', 'archive', 'archive_door_open', 'ink_with_shadow', 'archive_catalogued'),
('helia', 'observatory', 'moon_shutter_open', 'stars_forget', 'stars_counted'),
('echo', 'mirror', 'clockheart_prism_open', 'the_second_face', 'reflection_copied'),
('keeper', 'keeper', 'keeper_gate_open', 'the_clock_collects', 'crypt_locked');

INSERT INTO clues VALUES
('gear', 'gear.ppm', 1, 0, '#241D2F'),
('moon', 'moon.ppm', 2, 0, '#0D2440'),
('raven', 'raven.ppm', 3, 0, '#1D1727'),
('bell', 'bell.ppm', 4, 0, '#2B2112'),
('eye', 'eye.ppm', 5, 0, '#141B29'),
('bone', 'bone.ppm', 6, 0, '#2A2830'),
('key', 'key.ppm', 7, 0, '#1D2A24'),
('mirror', 'mirror.ppm', 8, 0, '#202737'),
('heart', 'heart.ppm', 9, 0, '#301923');

INSERT INTO beats VALUES
(1, 'gallery', 'display', 'gear', 'keeper_seal_set', 'first_panel_set'),
(2, 'mirror', 'name', 'mirror_shard', 'reflection_named', 'third_face_set'),
(3, 'archive', 'scribe', 'vellum_strip', 'archive_oath', 'vellum_clause_set'),
(4, 'gearwell', 'turn', 'brass_key', 'boiler_hatch_open', 'gear_teeth_aligned'),
(5, 'mirror', 'reflect', 'mirror', 'third_face_set', 'second_panel_set'),
(6, 'choir', 'reverse', 'choir_pin', 'hymn_reversed', 'choir_phrase_set'),
(7, 'keeper', 'forgive', 'keeper', 'crypt_reconciled', 'keeper_seal_set'),
(8, 'clockheart', 'chime', 'heart', 'keeper_seal_set', 'crypt_open'),
(9, 'boiler', 'stoke', 'soot_ribbon', 'furnace_bank_3', 'ash_pressure_set'),
(10, 'observatory', 'focus', 'silver_lens', 'stars_named', 'lunar_index_set'),
(11, 'clockheart', 'seat', 'pendulum_tooth', 'clockheart_prism_open', 'escapement_set'),
(12, 'ossuary', 'return', 'bone_token', 'bone_token_returned', 'pendulum_bones_set');

INSERT INTO migration_log VALUES (2, 'legacy_seed');
COMMIT;
]=]

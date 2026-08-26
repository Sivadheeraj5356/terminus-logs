-- RelicMaze authoritative dataset.
-- Loaded into the live PostgreSQL server. This file is NOT shipped in the
-- agent-visible image layer; the data is only reachable through the database.

BEGIN;

DROP TABLE IF EXISTS passages;
DROP TABLE IF EXISTS relics;
DROP TABLE IF EXISTS rooms;

CREATE TABLE rooms (
    room_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    biome         TEXT NOT NULL,
    base_light    INTEGER NOT NULL,
    locked        BOOLEAN NOT NULL DEFAULT FALSE,
    unlock_relic  TEXT
);

CREATE TABLE relics (
    relic_id      TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    room_id       TEXT NOT NULL REFERENCES rooms(room_id),
    rarity        TEXT NOT NULL,
    mass_g        INTEGER NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL,
    cursed        BOOLEAN NOT NULL DEFAULT FALSE,
    luminosity    NUMERIC(6,2) NOT NULL DEFAULT 0
);

CREATE TABLE passages (
    from_room     TEXT NOT NULL REFERENCES rooms(room_id),
    to_room       TEXT NOT NULL REFERENCES rooms(room_id),
    direction     TEXT NOT NULL,
    torch_cost    NUMERIC(6,2) NOT NULL,
    PRIMARY KEY (from_room, direction)
);

INSERT INTO rooms (room_id, name, biome, base_light, locked, unlock_relic) VALUES
    ('atrium',      'Sunken Atrium',        'flooded',  6, FALSE, NULL),
    ('gallery',     'Gallery of Whispers',  'cavern',   4, FALSE, NULL),
    ('forge',       'Emberforge Hollow',    'volcanic', 8, FALSE, NULL),
    ('vault',       'Vault of Echoes',      'crystal',  3, TRUE,  'silver-sigil'),
    ('garden',      'Petrified Garden',     'fungal',   5, FALSE, NULL),
    ('observatory', 'Starfall Observatory', 'astral',   2, TRUE,  'astrolabe-shard'),
    ('catacomb',    'Whisperbone Catacomb', 'ossuary',  1, FALSE, NULL),
    ('spring',      'Mercury Spring',       'toxic',    7, FALSE, NULL);

INSERT INTO relics (relic_id, name, room_id, rarity, mass_g, discovered_at, cursed, luminosity) VALUES
    ('silver-sigil',     'Silver Sigil',     'atrium',      'rare',      120, '2412-03-01 22:45:00+00', FALSE, 2.00),
    ('tide-pearl',       'Tide Pearl',       'atrium',      'common',     40, '2412-03-01 06:15:00+00', FALSE, 1.50),
    ('drowned-crown',    'Drowned Crown',    'atrium',      'epic',      300, '2412-02-28 23:50:00+00', TRUE,  3.00),
    ('echo-lens',        'Echo Lens',        'gallery',     'rare',       80, '2412-03-02 10:00:00+00', FALSE, 2.50),
    ('whisper-coin',     'Whisper Coin',     'gallery',     'common',     15, '2412-03-02 10:00:00+00', FALSE, 0.50),
    ('astrolabe-shard',  'Astrolabe Shard',  'gallery',     'epic',       60, '2412-03-01 12:30:00+00', FALSE, 2.00),
    ('ember-heart',      'Ember Heart',      'forge',       'legendary', 500, '2412-03-03 04:20:00+00', FALSE, 5.00),
    ('slag-idol',        'Slag Idol',        'forge',       'uncommon',  200, '2412-03-01 09:00:00+00', TRUE,  1.00),
    ('crystal-eye',      'Crystal Eye',      'vault',       'legendary',  90, '2412-03-02 21:10:00+00', FALSE, 4.00),
    ('resonant-bell',    'Resonant Bell',    'vault',       'rare',      350, '2412-03-02 21:10:00+00', FALSE, 2.00),
    ('spore-lantern',    'Spore Lantern',    'garden',      'uncommon',   70, '2412-03-01 18:40:00+00', FALSE, 3.50),
    ('petrified-rose',   'Petrified Rose',   'garden',      'common',     25, '2412-03-02 23:30:00+00', FALSE, 1.00),
    ('astral-compass',   'Astral Compass',   'observatory', 'epic',      110, '2412-03-04 01:05:00+00', FALSE, 2.50),
    ('bone-flute',       'Bone Flute',       'catacomb',    'common',     30, '2412-03-01 00:10:00+00', FALSE, 0.50),
    ('grave-ember',      'Grave Ember',      'catacomb',    'rare',       45, '2412-02-28 21:30:00+00', TRUE,  1.50),
    ('quicksilver-vial', 'Quicksilver Vial', 'spring',      'uncommon',   55, '2412-03-02 15:45:00+00', FALSE, 2.00),
    ('mercury-mirror',   'Mercury Mirror',   'spring',      'epic',      130, '2412-03-02 15:45:00+00', FALSE, 2.50);

INSERT INTO passages (from_room, to_room, direction, torch_cost) VALUES
    ('atrium',      'gallery',     'north', 1.00),
    ('atrium',      'forge',       'east',  1.50),
    ('atrium',      'catacomb',    'down',  2.00),
    ('gallery',     'vault',       'east',  2.50),
    ('gallery',     'garden',      'north', 1.00),
    ('forge',       'vault',       'north', 1.00),
    ('forge',       'spring',      'east',  1.50),
    ('garden',      'observatory', 'up',    3.00),
    ('catacomb',    'spring',      'east',  1.00),
    ('spring',      'forge',       'north', 1.00),
    ('vault',       'catacomb',    'down',  2.00),
    ('observatory', 'garden',      'down',  1.00);

COMMIT;

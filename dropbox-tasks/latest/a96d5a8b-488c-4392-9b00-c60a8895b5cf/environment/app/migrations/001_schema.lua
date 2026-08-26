return [=[
BEGIN IMMEDIATE;

CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    north TEXT REFERENCES rooms(id) DEFERRABLE INITIALLY DEFERRED,
    east TEXT REFERENCES rooms(id) DEFERRABLE INITIALLY DEFERRED,
    south TEXT REFERENCES rooms(id) DEFERRABLE INITIALLY DEFERRED,
    west TEXT REFERENCES rooms(id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE items (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL UNIQUE,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    unlocks TEXT NOT NULL UNIQUE,
    reusable INTEGER NOT NULL CHECK (reusable IN (0, 1))
);

CREATE TABLE locks (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    requires_item TEXT NOT NULL REFERENCES items(id),
    opens_flag TEXT NOT NULL UNIQUE
);

CREATE TABLE npcs (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id),
    gate_flag TEXT NOT NULL,
    dialogue_flag TEXT NOT NULL UNIQUE,
    grants_flag TEXT NOT NULL UNIQUE
);

CREATE TABLE clues (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL UNIQUE CHECK (position > 0),
    rotation INTEGER NOT NULL CHECK (rotation IN (0, 90, 180, 270)),
    matte TEXT NOT NULL CHECK (matte GLOB '#[0-9A-Fa-f]*' AND length(matte) = 7)
);

CREATE TABLE beats (
    position INTEGER PRIMARY KEY CHECK (position BETWEEN 1 AND 12),
    room_id TEXT NOT NULL REFERENCES rooms(id),
    action TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    requires_flag TEXT NOT NULL,
    emits_flag TEXT NOT NULL
);

CREATE TABLE migration_log (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO migration_log VALUES (1, 'schema');
COMMIT;
]=]

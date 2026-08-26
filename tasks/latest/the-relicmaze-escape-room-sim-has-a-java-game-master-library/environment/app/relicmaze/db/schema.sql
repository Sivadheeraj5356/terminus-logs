-- RelicMaze reference schema (structure only).
--
-- This file documents the shape of the live RelicMaze database. The actual
-- relic, room, and passage records live inside the running PostgreSQL server
-- and must be read from it directly; the row values are NOT reproduced here.

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

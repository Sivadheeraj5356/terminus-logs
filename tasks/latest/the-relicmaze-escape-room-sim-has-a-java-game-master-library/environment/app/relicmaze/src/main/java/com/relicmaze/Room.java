package com.relicmaze;

/** A maze chamber as stored in the {@code rooms} table. */
public final class Room {
    public final String id;
    public final String name;
    public final String biome;
    public final int baseLight;
    public final boolean locked;
    public final String unlockRelic; // nullable

    public Room(String id, String name, String biome, int baseLight,
                boolean locked, String unlockRelic) {
        this.id = id;
        this.name = name;
        this.biome = biome;
        this.baseLight = baseLight;
        this.locked = locked;
        this.unlockRelic = unlockRelic;
    }
}

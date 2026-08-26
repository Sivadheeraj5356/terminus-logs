package com.relicmaze;

import java.math.BigDecimal;
import java.time.Instant;

/** A relic as stored in the {@code relics} table. {@code discoveredAt} is an
 * absolute instant (the column is TIMESTAMPTZ, i.e. UTC). */
public final class Relic {
    public final String id;
    public final String name;
    public final String roomId;
    public final String rarity;
    public final int massG;
    public final Instant discoveredAt;
    public final boolean cursed;
    public final BigDecimal luminosity;

    public Relic(String id, String name, String roomId, String rarity, int massG,
                 Instant discoveredAt, boolean cursed, BigDecimal luminosity) {
        this.id = id;
        this.name = name;
        this.roomId = roomId;
        this.rarity = rarity;
        this.massG = massG;
        this.discoveredAt = discoveredAt;
        this.cursed = cursed;
        this.luminosity = luminosity;
    }
}

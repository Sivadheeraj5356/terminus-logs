package com.relicmaze;

import java.math.BigDecimal;

/** A one-way corridor as stored in the {@code passages} table. */
public final class Passage {
    public final String fromRoom;
    public final String toRoom;
    public final String direction;
    public final BigDecimal torchCost;

    public Passage(String fromRoom, String toRoom, String direction, BigDecimal torchCost) {
        this.fromRoom = fromRoom;
        this.toRoom = toRoom;
        this.direction = direction;
        this.torchCost = torchCost;
    }
}

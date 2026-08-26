package com.relicmaze;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** An immutable snapshot of the RelicMaze database, loaded once per resolve. */
public final class World {
    public final Map<String, Room> rooms;
    public final Map<String, Relic> relics;
    public final List<Passage> passages;

    public World(Map<String, Room> rooms, Map<String, Relic> relics, List<Passage> passages) {
        this.rooms = rooms;
        this.relics = relics;
        this.passages = passages;
    }

    /** Relics whose home room (per the database) is {@code roomId}. */
    public List<Relic> relicsHomedIn(String roomId) {
        List<Relic> out = new ArrayList<>();
        for (Relic r : relics.values()) {
            if (r.roomId.equals(roomId)) {
                out.add(r);
            }
        }
        return out;
    }

    /** Passages that leave {@code roomId}. */
    public List<Passage> passagesFrom(String roomId) {
        List<Passage> out = new ArrayList<>();
        for (Passage p : passages) {
            if (p.fromRoom.equals(roomId)) {
                out.add(p);
            }
        }
        return out;
    }

    public Passage passage(String roomId, String direction) {
        for (Passage p : passages) {
            if (p.fromRoom.equals(roomId) && p.direction.equals(direction)) {
                return p;
            }
        }
        return null;
    }

    public static Map<String, Room> emptyRoomMap() {
        return new LinkedHashMap<>();
    }
}

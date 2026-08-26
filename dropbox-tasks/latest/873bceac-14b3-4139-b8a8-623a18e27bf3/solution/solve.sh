#!/bin/bash
# Oracle solution for the RelicMaze resolver task.
# Writes the complete Resolver.java implementation into the starter library
# and compiles it. The verifier recompiles from source, so writing the file is
# what matters; the compile here is a sanity check.
set -euo pipefail

RESOLVER=/app/relicmaze/src/main/java/com/relicmaze/Resolver.java

cat > "$RESOLVER" <<'JAVA'
package com.relicmaze;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * RelicMaze game master. See the Keeper Manual for the authoritative rules.
 */
public final class Resolver implements Oracle {

    private static final String[] COMPASS = {"north", "east", "south", "west", "up", "down"};
    private static final BigDecimal HALF = new BigDecimal("0.5");
    private static final BigDecimal FLOOR = new BigDecimal("0.1");

    private static final Pattern P_SEAL  = Pattern.compile("^RUN keeper seal ([a-z0-9-]+)$");
    private static final Pattern P_CURSE = Pattern.compile("^RUN keeper curse ([a-z0-9-]+)$");
    private static final Pattern P_TAX   = Pattern.compile("^ENV torch_tax=(-?[0-9]+(?:\\.[0-9]+)?)$");
    private static final Pattern P_OMEN  = Pattern.compile("^LABEL omen=\"(.*)\"$");

    @Override
    public Response resolve(Request request) throws Exception {
        CapsuleSpec spec = CapsuleSpec.load(request.capsuleRef());
        World world = Db.loadWorld();

        // --- capsule directives ---------------------------------------------
        Map<String, String> labels = spec.labels();
        String startRoom = labels.get("relicmaze.start_room");
        String goalRoom = labels.get("relicmaze.goal_room");
        BigDecimal torch = new BigDecimal(labels.get("relicmaze.torch"));
        int tzOffsetMin = Integer.parseInt(labels.get("relicmaze.keeper_tz_offset_minutes"));
        long capacity = labels.containsKey("relicmaze.carry_capacity")
                ? Long.parseLong(labels.get("relicmaze.carry_capacity")) : Long.MAX_VALUE;

        TreeSet<String> sealed = new TreeSet<>();
        TreeSet<String> forcedCursed = new TreeSet<>();
        BigDecimal torchTax = BigDecimal.ZERO;
        String omen = "The maze breathes.";
        for (String line : spec.history()) {
            String s = line.trim();
            Matcher m;
            if ((m = P_SEAL.matcher(s)).matches()) {
                sealed.add(m.group(1));
            } else if ((m = P_CURSE.matcher(s)).matches()) {
                forcedCursed.add(m.group(1));
            } else if ((m = P_TAX.matcher(s)).matches()) {
                torchTax = new BigDecimal(m.group(1));
            } else if ((m = P_OMEN.matcher(s)).matches()) {
                omen = m.group(1);
            }
        }

        // --- replay the transcript ------------------------------------------
        Map<String, String> relicLocation = new LinkedHashMap<>();
        for (Relic r : world.relics.values()) {
            relicLocation.put(r.id, r.roomId);
        }
        TreeSet<String> inventory = new TreeSet<>();
        long carriedMass = 0;
        String room = startRoom;

        for (String raw : request.transcript()) {
            String cmd = raw.trim();
            String[] parts = cmd.split("\\s+");
            if (parts.length == 0 || parts[0].isEmpty()) {
                continue;
            }
            String verb = parts[0].toLowerCase();
            String arg = parts.length > 1 ? parts[1] : null;

            if (verb.equals("go") && arg != null) {
                String dir = arg.toLowerCase();
                Passage p = world.passage(room, dir);
                if (p == null) {
                    continue;
                }
                Room target = world.rooms.get(p.toRoom);
                if (target == null) {
                    continue;
                }
                if (target.locked && !inventory.contains(target.unlockRelic)) {
                    continue;
                }
                BigDecimal cost = effectiveToll(p.torchCost, torchTax,
                        cursedCarried(world, inventory, forcedCursed),
                        legendaryCarried(world, inventory));
                if (torch.compareTo(cost) < 0) {
                    continue;
                }
                torch = torch.subtract(cost);
                room = target.id;
            } else if (verb.equals("take") && arg != null) {
                String id = arg;
                Relic r = world.relics.get(id);
                if (r != null && room.equals(relicLocation.get(id)) && !sealed.contains(id)
                        && carriedMass + r.massG <= capacity) {
                    relicLocation.remove(id);
                    inventory.add(id);
                    carriedMass += r.massG;
                }
            } else if (verb.equals("drop") && arg != null) {
                String id = arg;
                if (inventory.contains(id)) {
                    inventory.remove(id);
                    carriedMass -= world.relics.get(id).massG;
                    relicLocation.put(id, room);
                }
            }
        }

        // --- final state and pack burden ------------------------------------
        Room here = world.rooms.get(room);
        boolean darkness = torch.compareTo(BigDecimal.ZERO) <= 0;
        int cursedCarried = cursedCarried(world, inventory, forcedCursed);
        boolean legendaryCarried = legendaryCarried(world, inventory);

        List<Relic> present = new ArrayList<>();
        for (Relic r : world.relics.values()) {
            if (room.equals(relicLocation.get(r.id))) {
                present.add(r);
            }
        }
        present.sort(relicOrder(forcedCursed));

        // --- narration ------------------------------------------------------
        List<String> lines = new ArrayList<>();
        lines.add("== " + here.name + " [" + here.biome + "] ==");
        lines.add("Omen: " + omen);

        if (darkness) {
            lines.add("Light: 0.0 lumens");
            lines.add("Relics:");
            lines.add("  (too dark to discern)");
        } else {
            lines.add("Light: " + fmt1(computeLight(here, present, forcedCursed)) + " lumens");
            lines.add("Relics:");
            if (present.isEmpty()) {
                lines.add("  (no relics here)");
            } else {
                for (Relic r : present) {
                    StringBuilder sb = new StringBuilder();
                    sb.append("  - ").append(r.name)
                      .append(" <").append(r.rarity).append("> ")
                      .append(r.massG).append("g");
                    if (isCursed(r, forcedCursed)) {
                        sb.append(" (cursed)");
                    }
                    if (sealed.contains(r.id)) {
                        sb.append(" (sealed)");
                    }
                    lines.add(sb.toString());
                }
            }
            Relic freshest = freshest(present, sealed);
            if (freshest != null) {
                lines.add("Freshest: " + freshest.name + " @ "
                        + keeperTime(freshest.discoveredAt, tzOffsetMin) + " KST");
            }
        }

        lines.add("Exits:");
        List<Passage> exits = world.passagesFrom(room);
        exits.sort(Comparator.comparingInt(p -> compassRank(p.direction)));
        if (exits.isEmpty()) {
            lines.add("  (no exits)");
        } else {
            for (Passage p : exits) {
                BigDecimal cost = effectiveToll(p.torchCost, torchTax, cursedCarried, legendaryCarried);
                String disp;
                if (darkness) {
                    disp = "???";
                } else {
                    Room target = world.rooms.get(p.toRoom);
                    if (target.locked && !inventory.contains(target.unlockRelic)) {
                        disp = "sealed gate";
                    } else {
                        disp = target.name;
                    }
                }
                lines.add("  - " + p.direction + ": " + disp + " (torch " + fmt1(cost) + ")");
            }
        }

        lines.add("Torch: " + fmt1(darkness ? BigDecimal.ZERO : torch) + " units");
        lines.add("Inventory: " + (inventory.isEmpty() ? "(empty)" : String.join(", ", inventory)));

        String routeLine = route(world, room, goalRoom, torchTax, inventory,
                cursedCarried, legendaryCarried, darkness);
        if (routeLine != null) {
            lines.add(routeLine);
        }

        String narration = String.join("\n", lines);

        // --- actions --------------------------------------------------------
        List<String> actions = new ArrayList<>();
        if (darkness) {
            actions.add("wait");
        } else {
            Relic cursedHere = null;
            for (Relic r : present) {
                if (isCursed(r, forcedCursed) && !sealed.contains(r.id)) {
                    cursedHere = r;
                    break;
                }
            }
            if (cursedHere != null) {
                actions.add("inspect " + cursedHere.id);
            } else {
                Relic takeable = null;
                for (Relic r : present) {
                    if (!sealed.contains(r.id) && !isCursed(r, forcedCursed)
                            && carriedMass + r.massG <= capacity) {
                        takeable = r;
                        break;
                    }
                }
                if (takeable != null) {
                    actions.add("take " + takeable.id);
                }
                Passage move = bestMove(world, room, torch, torchTax, inventory,
                        cursedCarried, legendaryCarried);
                if (move != null) {
                    actions.add("go " + move.direction);
                }
                if (actions.isEmpty()) {
                    actions.add("wait");
                }
            }
        }

        return new Response(narration, actions);
    }

    // --- burden of the pack -------------------------------------------------

    private static int cursedCarried(World world, TreeSet<String> inventory, TreeSet<String> forcedCursed) {
        int n = 0;
        for (String id : inventory) {
            if (isCursed(world.relics.get(id), forcedCursed)) {
                n++;
            }
        }
        return n;
    }

    private static boolean legendaryCarried(World world, TreeSet<String> inventory) {
        for (String id : inventory) {
            if (world.relics.get(id).rarity.equals("legendary")) {
                return true;
            }
        }
        return false;
    }

    private static BigDecimal effectiveToll(BigDecimal passageCost, BigDecimal torchTax,
                                            int cursedCarried, boolean legendaryCarried) {
        BigDecimal t = passageCost.add(torchTax).add(HALF.multiply(new BigDecimal(cursedCarried)));
        if (legendaryCarried) {
            t = t.subtract(HALF);
        }
        return t.compareTo(FLOOR) < 0 ? FLOOR : t;
    }

    // --- route (least-toll lock-gated path over the directed graph) ---------

    private static final class RouteRec {
        final String node;
        final BigDecimal cost;
        final int steps;
        final List<Integer> ranks;
        final List<String> dirs;

        RouteRec(String node, BigDecimal cost, int steps, List<Integer> ranks, List<String> dirs) {
            this.node = node;
            this.cost = cost;
            this.steps = steps;
            this.ranks = ranks;
            this.dirs = dirs;
        }
    }

    private static int compareRoute(RouteRec a, RouteRec b) {
        int c = a.cost.compareTo(b.cost);
        if (c != 0) {
            return c;
        }
        c = Integer.compare(a.steps, b.steps);
        if (c != 0) {
            return c;
        }
        int n = Math.min(a.ranks.size(), b.ranks.size());
        for (int i = 0; i < n; i++) {
            c = Integer.compare(a.ranks.get(i), b.ranks.get(i));
            if (c != 0) {
                return c;
            }
        }
        return Integer.compare(a.ranks.size(), b.ranks.size());
    }

    private static String route(World world, String room, String goal, BigDecimal torchTax,
                                TreeSet<String> inventory, int cursedCarried, boolean legendaryCarried,
                                boolean darkness) {
        if (darkness) {
            return "Route: ???";
        }
        if (goal == null) {
            return null;
        }
        if (room.equals(goal)) {
            return "Route: you stand at the goal";
        }

        Map<String, RouteRec> best = new HashMap<>();
        PriorityQueue<RouteRec> pq = new PriorityQueue<>(Resolver::compareRoute);
        pq.add(new RouteRec(room, BigDecimal.ZERO, 0, new ArrayList<>(), new ArrayList<>()));

        while (!pq.isEmpty()) {
            RouteRec cur = pq.poll();
            if (best.containsKey(cur.node)) {
                continue;
            }
            best.put(cur.node, cur);
            if (cur.node.equals(goal)) {
                break;
            }
            for (Passage p : world.passagesFrom(cur.node)) {
                Room target = world.rooms.get(p.toRoom);
                if (target.locked && !inventory.contains(target.unlockRelic)) {
                    continue;
                }
                if (best.containsKey(target.id)) {
                    continue;
                }
                List<Integer> ranks = new ArrayList<>(cur.ranks);
                ranks.add(compassRank(p.direction));
                List<String> dirs = new ArrayList<>(cur.dirs);
                dirs.add(p.direction);
                BigDecimal edge = effectiveToll(p.torchCost, torchTax, cursedCarried, legendaryCarried);
                pq.add(new RouteRec(target.id, cur.cost.add(edge), cur.steps + 1, ranks, dirs));
            }
        }

        RouteRec goalRec = best.get(goal);
        if (goalRec == null) {
            return "Route: no route";
        }
        return "Route: " + String.join(" ", goalRec.dirs) + " (torch " + fmt1(goalRec.cost) + ")";
    }

    // --- helpers ------------------------------------------------------------

    private static boolean isCursed(Relic r, TreeSet<String> forcedCursed) {
        return r.cursed || forcedCursed.contains(r.id);
    }

    private static int rarityRank(String rarity) {
        switch (rarity) {
            case "legendary": return 0;
            case "epic":      return 1;
            case "rare":      return 2;
            case "uncommon":  return 3;
            case "common":    return 4;
            default:          return 5;
        }
    }

    private static int compassRank(String dir) {
        for (int i = 0; i < COMPASS.length; i++) {
            if (COMPASS[i].equals(dir)) {
                return i;
            }
        }
        return COMPASS.length;
    }

    private static Comparator<Relic> relicOrder(TreeSet<String> forcedCursed) {
        return Comparator
                .comparingInt((Relic r) -> rarityRank(r.rarity))
                .thenComparing(r -> r.discoveredAt)
                .thenComparing(r -> r.id);
    }

    private static BigDecimal computeLight(Room here, List<Relic> present, TreeSet<String> forcedCursed) {
        BigDecimal light = new BigDecimal(here.baseLight);
        int cursedCount = 0;
        for (Relic r : present) {
            if (isCursed(r, forcedCursed)) {
                cursedCount++;
            } else {
                light = light.add(r.luminosity);
            }
        }
        light = light.subtract(HALF.multiply(new BigDecimal(cursedCount)));
        return light;
    }

    private static Relic freshest(List<Relic> present, TreeSet<String> sealed) {
        Relic best = null;
        for (Relic r : present) {
            if (sealed.contains(r.id)) {
                continue;
            }
            if (best == null) {
                best = r;
            } else {
                int c = r.discoveredAt.compareTo(best.discoveredAt);
                if (c > 0 || (c == 0 && r.id.compareTo(best.id) < 0)) {
                    best = r;
                }
            }
        }
        return best;
    }

    private static String keeperTime(Instant instant, int offsetMinutes) {
        OffsetDateTime odt = instant.atOffset(ZoneOffset.ofTotalSeconds(offsetMinutes * 60));
        return String.format("%02d:%02d", odt.getHour(), odt.getMinute());
    }

    private static Passage bestMove(World world, String room, BigDecimal torch, BigDecimal torchTax,
                                    TreeSet<String> inventory, int cursedCarried, boolean legendaryCarried) {
        Passage best = null;
        BigDecimal bestCost = null;
        for (Passage p : world.passagesFrom(room)) {
            Room target = world.rooms.get(p.toRoom);
            if (target.locked && !inventory.contains(target.unlockRelic)) {
                continue;
            }
            BigDecimal cost = effectiveToll(p.torchCost, torchTax, cursedCarried, legendaryCarried);
            if (torch.compareTo(cost) < 0) {
                continue;
            }
            if (best == null
                    || cost.compareTo(bestCost) < 0
                    || (cost.compareTo(bestCost) == 0
                        && compassRank(p.direction) < compassRank(best.direction))) {
                best = p;
                bestCost = cost;
            }
        }
        return best;
    }

    private static String fmt1(BigDecimal x) {
        return x.setScale(1, RoundingMode.HALF_UP).toPlainString();
    }
}
JAVA

echo "Wrote $RESOLVER"
cd /app/relicmaze
bash build.sh
echo "Oracle solution compiled."

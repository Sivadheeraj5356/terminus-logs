#!/bin/bash
set -euo pipefail
cd /app

# Get the lay of the land first.
ls -R /app

# The full rules. This is the part that actually decides the answer, so read it
# properly rather than guessing the sawmill from memory.
cat /app/docs/rules.md

# What the bench looks like right now.
cat /app/Main.java
cat /app/Sawmill.java

# A sample bench and a batch of rods to try things against.
cat /app/fixtures/mill.txt
cat /app/fixtures/rods.txt

# See the current behaviour before touching anything. The sketch scores a rod at
# the units of timber standing in it and reads one blade for every row, so it calls
# a lone rod of two a win and misses the way a gap flips the row.
javac -d /tmp/sawsplitclasses /app/Main.java /app/Sawmill.java
java -cp /tmp/sawsplitclasses Main /app/fixtures/mill.txt < /app/fixtures/rods.txt || true

# The mill file reading, the echo and the wording are fine as they stand. What is
# wrong is the reckoning. A rod's worth has to be worked up from the shorter rods,
# cut by cut, under the blade the row is set to, and there are two such tables: one
# for the heavy blade, where a cut eats a unit and the two rods add to one less than
# the rod, and one for the true blade, where a cut eats nothing. The gaps in the row
# pick the table. Replace the reckoning with that play.
cat > Sawmill.java << 'EOF'
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Arrays;

// The gosaw engine. It reads the mill file for the rod bound, then settles a batch by working
// each rod's worth up from the shorter rods under the blade the row is set to. longest is the
// greatest length any one rod may have at this bench; hasLongest says whether a bound was
// given at all.
public class Sawmill {
    long longest;
    boolean hasLongest;

    Sawmill() {
        this.longest = 0;
        this.hasLongest = false;
    }

    // allDigits reports whether s is one or more decimal digits and nothing else.
    static boolean allDigits(String s) {
        if (s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    // parseWhole reads a whole-number literal into a number, or null when the literal does not
    // hold one: an optional single leading + or - sign followed by one or more decimal digits,
    // naming a value that fits.
    static Long parseWhole(String tok) {
        String body = tok;
        if (!body.isEmpty() && (body.charAt(0) == '+' || body.charAt(0) == '-')) {
            body = body.substring(1);
        }
        if (!allDigits(body)) {
            return null;
        }
        try {
            return Long.parseLong(tok);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static String firstWord(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t') {
                return s.substring(0, i);
            }
        }
        return s;
    }

    // fields splits a line on runs of whitespace, dropping empty pieces.
    static String[] fields(String line) {
        String t = line.trim();
        if (t.isEmpty()) {
            return new String[0];
        }
        return t.split("\\s+");
    }

    // The worth of a rod has no closed form and is worked up from the shorter rods, cut by cut,
    // under whichever blade the row is set to. There are two tables. HEAVY is the worth on a
    // heavy blade, where a cut eats one unit and the two rods add to one less than the rod, so
    // only a rod of three or more can be sawn. TRUE_BLADE is the worth on a true blade, where a
    // cut eats nothing and the two rods add to the rod, so a rod of two can be sawn into two
    // ones and only a rod of one is finished. Each entry is the smallest whole number no single
    // cut leaves the rod at, built short before long.
    static int[] heavyTable = new int[]{0};
    static int heavyLen = 1;
    static int[] trueTable = new int[]{0};
    static int trueLen = 1;

    static void ensureHeavy(int n) {
        if (n < heavyLen) {
            return;
        }
        if (n >= heavyTable.length) {
            heavyTable = Arrays.copyOf(heavyTable, Math.max(n + 1, heavyTable.length * 2));
        }
        for (int m = heavyLen; m <= n; m++) {
            int bound = 4 * m + 8;
            boolean[] seen = new boolean[bound];
            for (int a = 1; a <= m - 2; a++) {
                int v = heavyTable[a] ^ heavyTable[m - 1 - a];
                if (v < bound) {
                    seen[v] = true;
                }
            }
            int mex = 0;
            while (mex < bound && seen[mex]) {
                mex++;
            }
            heavyTable[m] = mex;
            heavyLen = m + 1;
        }
    }

    static void ensureTrue(int n) {
        if (n < trueLen) {
            return;
        }
        if (n >= trueTable.length) {
            trueTable = Arrays.copyOf(trueTable, Math.max(n + 1, trueTable.length * 2));
        }
        for (int m = trueLen; m <= n; m++) {
            int bound = 4 * m + 8;
            boolean[] seen = new boolean[bound];
            for (int a = 1; a <= m - 1; a++) {
                int v = trueTable[a] ^ trueTable[m - a];
                if (v < bound) {
                    seen[v] = true;
                }
            }
            int mex = 0;
            while (mex < bound && seen[mex]) {
                mex++;
            }
            trueTable[m] = mex;
            trueLen = m + 1;
        }
    }

    // worth returns the worth of a rod of n units under the blade this row is set to. heavy
    // says the blade is heavy; a rod of nought units is a gap and is worth nought under either
    // blade.
    static long worth(long n, boolean heavy) {
        if (n <= 0) {
            return 0;
        }
        int k = (int) n;
        if (heavy) {
            ensureHeavy(k);
            return heavyTable[k];
        }
        ensureTrue(k);
        return trueTable[k];
    }

    // eval reads one batch line and reports the outcome for the player to saw. A line with no
    // fields, or any field that is not a whole-number literal, returns null and no output.
    String eval(String line) {
        String[] toks = fields(line);
        if (toks.length == 0) {
            return null;
        }
        long[] rods = new long[toks.length];
        for (int i = 0; i < toks.length; i++) {
            Long v = parseWhole(toks[i]);
            if (v == null) {
                return null;
            }
            rods[i] = v;
        }

        StringBuilder echo = new StringBuilder();
        boolean inRange = true;
        int gaps = 0;
        for (int i = 0; i < rods.length; i++) {
            if (i > 0) {
                echo.append(' ');
            }
            echo.append(Long.toString(rods[i]));
            if (rods[i] < 0 || (hasLongest && rods[i] > longest)) {
                inRange = false;
            }
            if (rods[i] == 0) {
                gaps++;
            }
        }
        String head = echo.toString() + " | ";

        if (!inRange) {
            return head + "ILLEGAL";
        }

        // The gaps set the blade: heavy when their count is even or nought, true when it is odd.
        boolean heavy = gaps % 2 == 0;

        long total = 0;
        for (long r : rods) {
            total ^= worth(r, heavy);
        }
        if (total == 0) {
            return head + "LOSS";
        }
        return head + "WIN " + winningCut(rods, total, heavy);
    }

    // winningCut renders one legal cut that leaves the opponent a batch of nought worth. The
    // batch passed in is a win, so such a cut exists. For each rod the worth the rest of the
    // row must match is fixed, and a cut is sought that brings that rod to it under the blade
    // in force: on a heavy blade the two rods add to one less than the rod and a rod of three
    // or more is needed, on a true blade they add to the rod and a rod of two or more is
    // needed.
    static String winningCut(long[] rods, long total, boolean heavy) {
        long minLen = heavy ? 3 : 2;
        for (int i = 0; i < rods.length; i++) {
            long r = rods[i];
            if (r < minLen) {
                continue;
            }
            long rest = total ^ worth(r, heavy);
            long sum = heavy ? r - 1 : r;
            for (long a = 1; a <= sum - 1; a++) {
                long b = sum - a;
                if ((worth(a, heavy) ^ worth(b, heavy)) == rest) {
                    return "cut rod " + (i + 1) + " into " + a + " and " + b;
                }
            }
        }
        return "";
    }

    // load reads the mill file and records the rod bound. Comments run from the first # to the
    // end of a line. A line beginning longest: reads the first word after it: a run of decimal
    // digits sets the bound, and anything else leaves the setting where it stood. The last
    // longest: line that sets a value stands, and a file that never sets one runs with no
    // bound.
    static Sawmill load(String path) throws IOException {
        String data = new String(Files.readAllBytes(Paths.get(path)));
        Sawmill m = new Sawmill();
        for (String raw : data.split("\n", -1)) {
            String line = raw;
            int i = line.indexOf('#');
            if (i >= 0) {
                line = line.substring(0, i);
            }
            line = line.trim();
            if (!line.startsWith("longest:")) {
                continue;
            }
            String w = firstWord(line.substring("longest:".length()).trim());
            if (allDigits(w)) {
                try {
                    m.longest = Long.parseLong(w);
                    m.hasLongest = true;
                } catch (NumberFormatException e) {
                    // a run of digits too large to hold leaves the setting where it stood
                }
            }
        }
        return m;
    }
}
EOF

# Sanity check: still builds, and the probe batches now read the way the rules say.
# A lone rod of two is a loss, the same two beside a gap is a win.
javac -d /tmp/sawsplitclasses /app/Main.java /app/Sawmill.java
java -cp /tmp/sawsplitclasses Main /app/fixtures/mill.txt < /app/fixtures/rods.txt

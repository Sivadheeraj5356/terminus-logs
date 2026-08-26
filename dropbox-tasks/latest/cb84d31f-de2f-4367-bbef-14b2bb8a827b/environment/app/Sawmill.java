import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;

// This is an early sketch of the gosaw engine. It reads the mill file, notes the longest rod
// the bench takes, folds the rod lengths together and reads a cut off the result. It settles
// the plain batches but scores a rod only by the units of timber standing in it, as if the
// bench were a plain heap of tokens, and it reads the one same blade for every row. It never
// accounts for the way a saw cut leaves the timber, nor for the gaps that set the blade, so it
// calls the close batches backwards once the cuts start to bite.
public class Sawmill {
    // longest is the greatest length any one rod may have; hasLongest says whether a bound was
    // given at all.
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

    // worth scores a single rod. This sketch reads a rod as worth the units of timber standing
    // in it.
    static long worth(long n) {
        if (n < 0) {
            return 0;
        }
        return n;
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
        for (int i = 0; i < rods.length; i++) {
            if (i > 0) {
                echo.append(' ');
            }
            echo.append(Long.toString(rods[i]));
            if (rods[i] < 0 || (hasLongest && rods[i] > longest)) {
                inRange = false;
            }
        }
        String head = echo.toString() + " | ";

        if (!inRange) {
            return head + "ILLEGAL";
        }

        long total = 0;
        for (long r : rods) {
            total ^= worth(r);
        }
        if (total == 0) {
            return head + "LOSS";
        }
        for (int i = 0; i < rods.length; i++) {
            long r = rods[i];
            if (r < 3) {
                continue;
            }
            long rest = total ^ worth(r);
            for (long a = 1; a <= r - 2; a++) {
                long b = r - 1 - a;
                if ((worth(a) ^ worth(b)) == rest) {
                    return head + "cut rod " + (i + 1) + " into " + a + " and " + b;
                }
            }
        }
        for (int i = 0; i < rods.length; i++) {
            if (rods[i] >= 3) {
                return head + "cut rod " + (i + 1) + " into " + 1 + " and " + (rods[i] - 2);
            }
        }
        return head + "WIN";
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

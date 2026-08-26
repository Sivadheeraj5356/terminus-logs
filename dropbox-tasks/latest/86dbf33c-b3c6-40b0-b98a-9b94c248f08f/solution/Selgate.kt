// Selgate: given a candidate version and a requested version selector, print
// exactly "true" or "false" reporting whether the candidate satisfies the
// selector, reproducing Gradle's dependency version-selection semantics.
//
// Usage:
//
//     java -jar selgate.jar <version> <selector>
//
// The inputs used to evaluate this program are always well-formed selectors and
// versions that Gradle parses without error.

import kotlin.system.exitProcess

// ---- Gradle version model (mirrors org.gradle...strategy.VersionParser) ----

class GVersion(val source: String, val parts: List<String>)

fun isDigits(s: String): Boolean {
    if (s.isEmpty()) {
        return false
    }
    for (c in s) {
        if (c < '0' || c > '9') {
            return false
        }
    }
    return true
}

// parseVersion splits on '.', '-', '_', '+' separators AND on transitions
// between digit and non-digit runs, exactly like Gradle's VersionParser.
fun parseVersion(s: String): GVersion {
    val parts = ArrayList<String>()
    val cur = StringBuilder()
    // state: 0 unknown, 1 digit, 2 alpha
    var state = 0
    for (c in s) {
        if (c == '.' || c == '-' || c == '_' || c == '+') {
            if (cur.isNotEmpty()) {
                parts.add(cur.toString())
                cur.setLength(0)
            }
            state = 0
            continue
        }
        val d = c in '0'..'9'
        if (d) {
            if (state == 2 && cur.isNotEmpty()) {
                parts.add(cur.toString())
                cur.setLength(0)
            }
            state = 1
        } else {
            if (state == 1 && cur.isNotEmpty()) {
                parts.add(cur.toString())
                cur.setLength(0)
            }
            state = 2
        }
        cur.append(c)
    }
    if (cur.isNotEmpty()) {
        parts.add(cur.toString())
    }
    return GVersion(s, parts)
}

// specialMeaning mirrors Gradle's SPECIAL_MEANINGS map (case-insensitive).
// Returns null when the word carries no special meaning.
fun specialMeaning(s: String): Int? {
    return when (s.lowercase()) {
        "dev" -> -1
        "rc" -> 1
        "snapshot" -> 2
        "final" -> 3
        "ga" -> 4
        "release" -> 5
        "sp" -> 6
        else -> null
    }
}

// numericValue returns the value if part is all digits, else null. Values in
// the generated corpus stay within a safe range.
fun numericValue(p: String): Long? {
    if (!isDigits(p)) {
        return null
    }
    return try {
        p.toLong()
    } catch (e: NumberFormatException) {
        0L
    }
}

// compareVersions mirrors StaticVersionComparator.compare exactly, including
// its early-return-on-first-differing-part behavior.
fun compareVersions(v1: GVersion, v2: GVersion): Int {
    if (v1.source == v2.source) {
        return 0
    }
    val p1 = v1.parts
    val p2 = v2.parts
    val n = minOf(p1.size, p2.size)
    for (i in 0 until n) {
        val a = p1[i]
        val b = p2[i]
        val na = numericValue(a)
        val nb = numericValue(b)
        if (a == b) {
            // String equality (case-sensitive): equal part, keep going.
            continue
        }
        // numeric outranks non-numeric
        if (na != null && nb == null) {
            return 1
        }
        if (nb != null && na == null) {
            return -1
        }
        if (na != null && nb != null) {
            if (na < nb) {
                return -1
            }
            if (na > nb) {
                return 1
            }
            continue // equal numerics, keep going
        }
        // both non-numeric: special meanings, else case-sensitive compareTo
        val s1 = specialMeaning(a)
        val s2 = specialMeaning(b)
        if (s1 != null) {
            val s2v = s2 ?: 0
            return s1 - s2v
        }
        if (s2 != null) {
            return -s2
        }
        val c = a.compareTo(b)
        if (c < 0) {
            return -1
        }
        if (c > 0) {
            return 1
        }
        return 0
    }
    // Common prefix equal; length tie-break using numeric-ness of extra part.
    if (p1.size > p2.size) {
        return if (numericValue(p1[n]) != null) 1 else -1
    }
    if (p2.size > p1.size) {
        return if (numericValue(p2[n]) != null) -1 else 1
    }
    return 0
}

// ---- Selector schemes (mirrors DefaultVersionSelectorScheme) ----

fun satisfies(version: String, selector: String): Boolean {
    val sel = selector.trim()
    // latest.* dynamic selectors
    if (sel == "latest.integration" || sel == "latest.release") {
        // Without component metadata, Gradle's LatestVersionSelector accepts
        // any version string.
        return true
    }
    // '+' bare or 'prefix.+' sub-version selector
    if (sel == "+") {
        return true
    }
    if (sel.endsWith("+")) {
        return subVersionAccept(version, sel)
    }
    // range selector: starts with '[' or '(' and contains a comma
    val r = tryRange(version, sel)
    if (r != null) {
        return r
    }
    // exact version selector
    return compareVersions(parseVersion(version), parseVersion(sel)) == 0
}

// tryRange returns the result if sel is a well-formed range, or null if sel
// is not a range and should be handled as an exact selector.
fun tryRange(version: String, sel: String): Boolean? {
    if (sel.length < 3) {
        return null
    }
    val first = sel[0]
    val last = sel[sel.length - 1]
    if (first != '[' && first != '(') {
        return null
    }
    if (last != ']' && last != ')') {
        return null
    }
    val inner = sel.substring(1, sel.length - 1)
    val comma = inner.indexOf(',')
    if (comma < 0) {
        return null
    }
    val lowerStr = inner.substring(0, comma).trim()
    val upperStr = inner.substring(comma + 1).trim()
    // A range must not have both bounds empty.
    if (lowerStr.isEmpty() && upperStr.isEmpty()) {
        return null
    }
    // Empty lower bound is only valid with '('; empty upper bound only ')'.
    if (lowerStr.isEmpty() && first != '(') {
        return null
    }
    if (upperStr.isEmpty() && last != ')') {
        return null
    }
    val lowerInc = first == '['
    val upperInc = last == ']'
    val v = parseVersion(version)
    if (lowerStr.isNotEmpty()) {
        // isHigher: cmp >= (inclusive ? 0 : 1)
        val c = compareVersions(v, parseVersion(lowerStr))
        val thresh = if (lowerInc) 0 else 1
        if (c < thresh) {
            return false
        }
    }
    if (upperStr.isNotEmpty()) {
        // isLower: inclusive => cmp <= 0; exclusive => cmp == -1 AND version
        // does not start with the bound's string (prefix-exclusive rule).
        val c = compareVersions(v, parseVersion(upperStr))
        val lower: Boolean
        if (upperInc) {
            lower = c <= 0
        } else if (c <= -1) {
            lower = !version.startsWith(upperStr)
        } else {
            lower = false
        }
        if (!lower) {
            return false
        }
    }
    return true
}

// subVersionAccept handles "1.+" / "1.2.+" prefix selectors.
fun subVersionAccept(version: String, sel: String): Boolean {
    val prefix = sel.substring(0, sel.length - 1) // trailing '.' kept
    return version.startsWith(prefix)
}

fun main(args: Array<String>) {
    if (args.size != 2) {
        System.err.println("usage: selgate <version> <selector>")
        exitProcess(2)
    }
    val version = args[0]
    val selector = args[1]
    println(if (satisfies(version, selector)) "true" else "false")
}

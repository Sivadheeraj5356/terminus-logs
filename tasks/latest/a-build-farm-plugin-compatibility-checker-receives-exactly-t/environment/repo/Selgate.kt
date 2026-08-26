// Selgate: given a candidate version and a requested version selector, print
// exactly "true" or "false" reporting whether the candidate satisfies the
// selector, reproducing Gradle's dependency version-selection semantics.
//
// Usage:
//
//     java -jar selgate.jar <version> <selector>
//
// On success it prints "true" or "false" followed by a newline. The inputs used
// to evaluate this program are always well-formed selectors and versions that
// Gradle parses without error.

import kotlin.system.exitProcess

// satisfies reports whether version satisfies selector following Gradle's
// version-selection rules.
fun satisfies(version: String, selector: String): Boolean {
    val sel = selector.trim()

    if (sel.startsWith("[") && sel.endsWith(",)")) {
        val lower = sel.substring(1, sel.length - 2)
        return compareNaive(parseNaive(version), parseNaive(lower)) >= 0
    }

    return compareNaive(parseNaive(version), parseNaive(sel)) == 0
}

// parseNaive returns the leading dotted numeric segments used by the baseline comparator.
fun parseNaive(s: String): List<Long> {
    val trimmed = s.trim()
    val out = ArrayList<Long>()
    for (p in trimmed.split(".")) {
        try {
            out.add(p.toLong())
        } catch (e: NumberFormatException) {
            break
        }
    }
    return out
}

fun compareNaive(a: List<Long>, b: List<Long>): Int {
    val n = maxOf(a.size, b.size)
    for (i in 0 until n) {
        val x = if (i < a.size) a[i] else 0L
        val y = if (i < b.size) b[i] else 0L
        if (x < y) {
            return -1
        }
        if (x > y) {
            return 1
        }
    }
    return 0
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

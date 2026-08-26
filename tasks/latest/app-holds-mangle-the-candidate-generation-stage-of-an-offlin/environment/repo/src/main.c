/* main.c — command-line driver for the mangle candidate generator.
 *
 *   mangle <rulefile> <wordlist>
 *
 * For every word in <wordlist>, in file order, each rule in <rulefile> is
 * applied to that word in file order. Every produced candidate is written to
 * standard output followed by a single newline. A (word, rule) pair that
 * yields no candidate (a reject or a malformed rule) emits nothing. The output
 * is therefore the concatenation, word-major then rule-minor, of all surviving
 * candidates. */
#include "mangle.h"

#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <rulefile> <wordlist>\n", argv[0]);
        return 2;
    }

    int nrules = 0, nwords = 0;
    char **rules = read_lines(argv[1], 1, &nrules);
    char **words = read_lines(argv[2], 0, &nwords);

    char out[CAND_MAX];

    for (int w = 0; w < nwords; w++) {
        int in_len = (int)strlen(words[w]);
        if (in_len >= CAND_MAX) {
            continue; /* words at or past the working limit are skipped */
        }
        for (int r = 0; r < nrules; r++) {
            int rule_len = (int)strlen(rules[r]);
            memset(out, 0, sizeof(out));
            int rc = apply_rule(rules[r], rule_len, words[w], in_len, out);
            if (rc < 0) {
                continue; /* no candidate for this pair */
            }
            fwrite(out, 1, (size_t)rc, stdout);
            fputc('\n', stdout);
        }
    }

    free_lines(rules, nrules);
    free_lines(words, nwords);
    return 0;
}

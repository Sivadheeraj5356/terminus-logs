/* unit.c — small behavioural checks for the rule engine, runnable with
 * `make test`. These cover a few basic functions so the engine can be
 * exercised during development; they are not the full conformance suite. */
#include "../src/mangle.h"
#include "../src/rules.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

/* Apply `rule` to `word` and check the produced candidate equals `want`
 * (length `want_len`), or that no candidate is produced when want == NULL. */
static void check(const char *rule, const char *word,
                  const char *want, int want_len) {
    char out[CAND_MAX];
    memset(out, 0, sizeof(out));
    int rc = apply_rule(rule, (int)strlen(rule), word, (int)strlen(word), out);
    if (want == NULL) {
        if (rc >= 0) {
            printf("FAIL %-8s %-12s: expected no candidate, got %d bytes\n",
                   rule, word, rc);
            failures++;
        }
        return;
    }
    if (rc != want_len || memcmp(out, want, (size_t)want_len) != 0) {
        printf("FAIL %-8s %-12s: got '%.*s' (%d), want '%.*s' (%d)\n",
               rule, word, rc < 0 ? 0 : rc, out, rc, want_len, want, want_len);
        failures++;
    }
}

int main(void) {
    /* argument decoding */
    if (rule_arg_value('7') != 7 || rule_arg_value('A') != 10 ||
        rule_arg_value('Z') != 35 || rule_arg_value('a') != -1) {
        printf("FAIL rule_arg_value\n");
        failures++;
    }

    check("l", "PassWord", "password", 8);
    check("u", "PassWord", "PASSWORD", 8);
    check("c", "passWORD", "Password", 8);
    check("r", "abc", "cba", 3);
    check("$9", "cat", "cat9", 4);
    check("^Z", "cat", "Zcat", 4);
    check(":", "cat", "cat", 3);
    check("'2", "abcdef", "ab", 2);   /* truncate to length 2 */
    check(">5", "cat", NULL, 0);       /* reject: length below 5 */

    if (failures == 0) {
        printf("all unit checks passed\n");
        return 0;
    }
    printf("%d unit check(s) failed\n", failures);
    return 1;
}

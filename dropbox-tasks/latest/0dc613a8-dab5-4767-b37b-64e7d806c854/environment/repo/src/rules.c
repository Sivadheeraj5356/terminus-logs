/* rules.c — the rule engine.
 *
 * This is the component to implement. `apply_rule` currently recognises only
 * the no-op rule and otherwise returns the word unchanged, so most rules pass
 * their input straight through. Implement the full function set described in
 * docs/rules.md: the case, edit, insertion/deletion, extraction, replacement,
 * duplication, swap, character-arithmetic, memory and reject functions, plus
 * the shared position-argument decoding and the reject/malformed handling that
 * suppresses a candidate. */
#include "rules.h"

#include <string.h>

int rule_arg_value(unsigned char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'A' && c <= 'Z') {
        return c - 'A' + 10;
    }
    return -1;
}

int apply_rule(const char *rule, int rule_len,
               const char *in, int in_len, char *out) {
    /* A candidate begins as a copy of the input word. */
    int out_len = in_len;
    memcpy(out, in, (size_t)out_len);

    for (int rp = 0; rp < rule_len; rp++) {
        char op = rule[rp];
        switch (op) {
            case ':': /* no-op */
                break;
            default:
                /* TODO: implement the remaining rule functions. Until then an
                 * unrecognised function leaves the candidate unchanged. */
                break;
        }
    }

    return out_len;
}

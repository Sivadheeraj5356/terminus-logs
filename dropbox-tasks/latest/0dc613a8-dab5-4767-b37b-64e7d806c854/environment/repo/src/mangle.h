/* mangle.h — shared definitions for the candidate generator. */
#ifndef MANGLE_H
#define MANGLE_H

#include <stddef.h>

/* Maximum working length of a candidate, matching the reference tool. A word
 * or intermediate result that reaches this size is left unchanged by the
 * length-growing functions. */
#define CAND_MAX 256

/* Return codes from apply_rule(). A non-negative value is the length of the
 * produced candidate in `out`. A negative value means no candidate is produced
 * for this (word, rule) pair and nothing is emitted. */
#define RULE_OK          0   /* and any positive length */
#define RULE_SKIP_SYNTAX (-1)
#define RULE_SKIP_REJECT (-2)

/* Apply one rule line to one input word.
 *
 *   rule / rule_len : the rule line (a sequence of functions), not NUL-reliant
 *   in   / in_len   : the input word (0 <= in_len < CAND_MAX)
 *   out             : caller-provided buffer of CAND_MAX bytes, pre-zeroed
 *
 * Returns the produced length (>= 0) written into `out`, or a negative
 * RULE_SKIP_* code when the pair yields no output. Defined in rules.c. */
int apply_rule(const char *rule, int rule_len,
               const char *in, int in_len, char *out);

/* wordio.c — line readers. Each returns a heap array of NUL-terminated lines
 * and writes the count through `count`. Trailing CR/LF are stripped. When
 * `drop_rule_lines` is nonzero, empty lines and lines beginning with '#' are
 * omitted (rule-file convention). Caller frees with free_lines(). */
char **read_lines(const char *path, int drop_rule_lines, int *count);
void   free_lines(char **lines, int count);

#endif /* MANGLE_H */

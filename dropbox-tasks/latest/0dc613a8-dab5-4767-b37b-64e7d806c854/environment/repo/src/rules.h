/* rules.h — the rule engine.
 *
 * A rule line is a sequence of single-character functions, each optionally
 * followed by fixed inline arguments (a position, a character, or both). The
 * engine applies the functions left to right to a mutable candidate that
 * starts as a copy of the input word. See docs/rules.md for the function set
 * and the exact behaviour of every function, including its argument encoding
 * and its behaviour at the ends of the candidate. */
#ifndef RULES_H
#define RULES_H

#include "mangle.h"

/* Decode one position/count argument character as the reference tool does.
 * Digits 0-9 map to 0-9 and the upper-case letters A-Z map to 10-35; every
 * other byte is invalid. Exposed for the unit tests. */
int rule_arg_value(unsigned char c);

#endif /* RULES_H */

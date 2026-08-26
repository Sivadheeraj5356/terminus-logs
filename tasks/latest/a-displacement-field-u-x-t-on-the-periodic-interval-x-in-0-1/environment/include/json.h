#ifndef TRANSPORT_JSON_H
#define TRANSPORT_JSON_H

/* Minimal reader for the flat JSON input used by this project. Every key is
 * unique, so each accessor locates the key text and reads the value following
 * the next colon. These are input-handling helpers only; they hold no numerics.
 * On a malformed or missing field the program prints a diagnostic and exits. */

/* Read an entire file into a NUL-terminated heap buffer. Returns NULL on
 * failure; on success *out_size receives the byte length (excluding the NUL). */
char *json_read_file(const char *path, long *out_size);

/* Scalar value that follows "key": . */
double json_scalar(const char *s, const char *key);

/* Scalar value rounded to the nearest integer. */
int json_int(const char *s, const char *key);

/* Numbers from the "[...]" array that follows "key":. Writes up to maxn values
 * into buf and returns the count actually read. */
int json_array(const char *s, const char *key, double *buf, int maxn);

/* String value that follows "key":, copied (without quotes) into buf. */
void json_string(const char *s, const char *key, char *buf, int maxn);

#endif /* TRANSPORT_JSON_H */

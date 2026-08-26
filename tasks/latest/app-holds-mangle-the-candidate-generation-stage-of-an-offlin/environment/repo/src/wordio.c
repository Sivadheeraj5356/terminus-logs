/* wordio.c — read a rule file or a wordlist into an array of lines.
 *
 * Lines are delimited by '\n'; a trailing '\r' (DOS line ending) and the '\n'
 * itself are stripped. For rule files, empty lines and lines whose first byte
 * is '#' are dropped, so a rule file may carry blank separators and comments.
 * Words and rules used by this tool are plain text without embedded NULs. */
#include "mangle.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_CAP (1 << 20)

char **read_lines(const char *path, int drop_rule_lines, int *count) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        exit(2);
    }

    char **lines = NULL;
    int n = 0, cap = 0;
    char *buf = malloc(LINE_CAP);
    if (!buf) {
        exit(2);
    }

    while (fgets(buf, LINE_CAP, f)) {
        int len = (int)strlen(buf);
        while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r')) {
            len--;
        }
        buf[len] = '\0';

        if (drop_rule_lines) {
            if (len == 0) {
                continue;
            }
            if (buf[0] == '#') {
                continue;
            }
        }

        if (n == cap) {
            cap = cap ? cap * 2 : 64;
            lines = realloc(lines, (size_t)cap * sizeof(char *));
            if (!lines) {
                exit(2);
            }
        }
        lines[n] = malloc((size_t)len + 1);
        if (!lines[n]) {
            exit(2);
        }
        memcpy(lines[n], buf, (size_t)len + 1);
        n++;
    }

    free(buf);
    fclose(f);
    *count = n;
    return lines;
}

void free_lines(char **lines, int count) {
    for (int i = 0; i < count; i++) {
        free(lines[i]);
    }
    free(lines);
}

#include "parse_tok.h"

#include <stdio.h>
#include <string.h>

int pp_env_value(const char *path, const char *key, char *out, size_t cap)
{
    FILE *fp = fopen(path, "r");
    char line[512];
    size_t klen;
    if (!fp || key == NULL || out == NULL || cap == 0) {
        if (fp) {
            fclose(fp);
        }
        return -1;
    }
    klen = strlen(key);
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, key, klen) == 0 && line[klen] == '=') {
            char *val = line + klen + 1;
            val[strcspn(val, "\r\n")] = '\0';
            snprintf(out, cap, "%s", val);
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int pp_token_count(const char *line)
{
    int n = 0;
    int in = 0;
    if (line == NULL) {
        return 0;
    }
    for (const char *p = line; *p; p++) {
        if (*p == ' ' || *p == '\t') {
            in = 0;
        } else if (!in) {
            in = 1;
            n++;
        }
    }
    return n;
}

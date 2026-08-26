/* Sandbox self-test probe (verifier-owned; never shipped to the agent).
 *
 * Attempts to read a protected key file and records the outcome, so the suite can
 * prove that a program executed under the unprivileged grading drop cannot reach a
 * root-only asset - the mechanism that stops a hostile candidate binary, or a
 * build-time shell escape, from reading the reference, fixtures, or tolerances
 * under /tests. argv[1] = key path, argv[2] = verdict output path. */
#include <stdio.h>

int main(int argc, char **argv) {
    if (argc < 3) return 2;
    FILE *out = fopen(argv[2], "w");
    if (!out) return 3;
    FILE *k = fopen(argv[1], "r");
    if (!k) {
        fprintf(out, "BLOCKED\n");
    } else {
        char buf[64];
        size_t n = fread(buf, 1, sizeof(buf) - 1, k);
        buf[n] = '\0';
        fprintf(out, "LEAK:%s\n", buf);
        fclose(k);
    }
    fclose(out);
    return 0;
}

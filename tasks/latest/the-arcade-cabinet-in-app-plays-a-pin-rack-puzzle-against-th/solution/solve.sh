#!/usr/bin/env bash

set -euo pipefail
cd /app

WORK="$(mktemp -d)"

cat > "$WORK/probe.c" <<'PROBE_EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

static int to_cab, from_cab;
static pid_t cab;
static char buf[8192];
static int blen, bpos;

static void open_cab(const char *path)
{
    int a[2], b[2];
    if (pipe(a) || pipe(b)) exit(2);
    cab = fork();
    if (cab < 0) exit(2);
    if (cab == 0) {
        dup2(a[0], 0);
        dup2(b[1], 1);
        close(a[0]); close(a[1]); close(b[0]); close(b[1]);
        execl(path, path, (char *) NULL);
        _exit(127);
    }
    close(a[0]);
    close(b[1]);
    to_cab = a[1];
    from_cab = b[0];
    blen = bpos = 0;
}

static int cab_line(char *dst, int cap)
{
    int n = 0;
    for (;;) {
        while (bpos < blen) {
            char ch = buf[bpos++];
            if (ch == '\n') { dst[n] = 0; return 1; }
            if (n < cap - 1) dst[n++] = ch;
        }
        blen = (int) read(from_cab, buf, sizeof(buf));
        bpos = 0;
        if (blen <= 0) return 0;
    }
}

static void cab_send(const char *s)
{
    if (write(to_cab, s, strlen(s)) < 0) exit(2);
}

static int drain(char *first, int cap)
{
    char reply[256];
    int n = 0;
    first[0] = 0;
    for (;;) {
        if (!cab_line(reply, sizeof(reply))) exit(2);
        if (strcmp(reply, "END") == 0) return n;
        if (n == 0) snprintf(first, cap, "%s", reply);
        n++;
    }
}

static int set_rack(int f, int c, int n1, int n2)
{
    char cmd[128], first[256];
    if (n2 > 0) snprintf(cmd, sizeof(cmd), "RACK %d %d %d %d\n", f, c, n1, n2);
    else snprintf(cmd, sizeof(cmd), "RACK %d %d %d\n", f, c, n1);
    cab_send(cmd);
    drain(first, sizeof(first));
    return strncmp(first, "READY", 5) == 0;
}

static int try_throw(int lane, int pins, int left, int *nf, int *nc)
{
    char cmd[128], first[256];
    snprintf(cmd, sizeof(cmd), "THROW %d %d %d\n", lane, pins, left);
    cab_send(cmd);
    drain(first, sizeof(first));
    if (strncmp(first, "OK", 2) != 0) return 0;
    if (sscanf(first, "OK %d %d", nf, nc) != 2) exit(2);
    return 1;
}

int main(int argc, char **argv)
{
    const char *cabinet = (argc > 1) ? argv[1] : "/app/cabinet/skittle";
    const char *out = (argc > 2) ? argv[2] : "/app/cabinet_model.txt";
    int faces = 0, latches = 0, maxpins = 0;
    int f, c, p, nf, nc;
    int rot[8], code[8][2], seen_rot[8], seen_code[8][2];
    FILE *fp;

    open_cab(cabinet);

    for (f = 0; f < 16; f++) {
        if (!set_rack(f, 0, 12, 0)) break;
        faces = f + 1;
    }
    for (c = 0; c < 16; c++) {
        if (!set_rack(0, c, 12, 0)) break;
        latches = c + 1;
    }
    for (p = 1; p <= 8; p++) {
        int ok = 0;
        for (f = 0; f < faces && !ok; f++)
            for (c = 0; c < latches && !ok; c++) {
                if (!set_rack(f, c, 20, 0)) continue;
                if (try_throw(1, p, 0, &nf, &nc)) ok = 1;
            }
        if (!ok) break;
        maxpins = p;
    }

    memset(seen_rot, 0, sizeof(seen_rot));
    memset(seen_code, 0, sizeof(seen_code));

    fp = fopen(out, "w");
    if (!fp) exit(2);
    fprintf(fp, "FACES %d\n", faces);
    fprintf(fp, "LATCHES %d\n", latches);
    fprintf(fp, "MAXPINS %d\n", maxpins);

    for (f = 0; f < faces; f++) {
        for (c = 0; c < latches; c++) {
            for (p = 1; p <= maxpins; p++) {
                int ok;
                if (!set_rack(f, c, 20, 0)) exit(2);
                ok = try_throw(1, p, 0, &nf, &nc);
                fprintf(fp, "PINOK %d %d %d %d\n", f, c, p, ok);
                if (ok && !seen_rot[p]) {
                    rot[p] = ((nf - f) % faces + faces) % faces;
                    seen_rot[p] = 1;
                }
                if (ok && !seen_code[p][0]) {
                    code[p][0] = nc;
                    seen_code[p][0] = 1;
                }
            }
            {
                int ok1, ok2;
                if (!set_rack(f, c, 20, 0)) exit(2);
                ok1 = try_throw(1, 1, 7, &nf, &nc);
                fprintf(fp, "SPLITONE %d %d %d\n", f, c, ok1);
                if (ok1 && !seen_code[1][1]) {
                    code[1][1] = nc;
                    seen_code[1][1] = 1;
                }
                if (ok1) {
                    for (p = 2; p <= maxpins; p++) {
                        if (!set_rack(f, c, 20, 0)) exit(2);
                        if (try_throw(1, p, 7, &nf, &nc) && !seen_code[p][1]) {
                            code[p][1] = nc;
                            seen_code[p][1] = 1;
                        }
                    }
                }
                if (!set_rack(f, c, 20, 6)) exit(2);
                ok2 = try_throw(1, 1, 7, &nf, &nc);
                fprintf(fp, "SPLITTWO %d %d %d\n", f, c, ok2);
            }
        }
    }

    for (p = 1; p <= maxpins; p++) {
        fprintf(fp, "ROT %d %d\n", p, seen_rot[p] ? rot[p] : 0);
        fprintf(fp, "CODE %d 0 %d\n", p, seen_code[p][0] ? code[p][0] : 0);
        fprintf(fp, "CODE %d 1 %d\n", p, seen_code[p][1] ? code[p][1] : 0);
    }

    fclose(fp);
    cab_send("QUIT\n");
    close(to_cab);
    waitpid(cab, NULL, 0);
    printf("faces=%d latches=%d maxpins=%d\n", faces, latches, maxpins);
    return 0;
}
PROBE_EOF

cat > "$WORK/entry.c" <<'ENTRY_EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXF 16
#define MAXC 16
#define MAXP 8
#define RW 220

static int FACES, LATCHES, MAXPINS;
static int pinok[MAXF][MAXC][MAXP];
static int splitone[MAXF][MAXC];
static int splittwo[MAXF][MAXC];
static int rot[MAXP];
static int codemap[MAXP][2];

static unsigned char *reach;
static int PER, PRE;
static long long LIM;

static int rx(int a, int b, int f, int c)
{
    int t;
    if (a < b) { t = a; a = b; b = t; }
    return reach[(((size_t) a * (RW + 1) + b) * FACES + f) * LATCHES + c];
}

static void load_model(const char *path)
{
    FILE *fp = fopen(path, "r");
    char key[32];
    char line[128];
    int a, b, c, d;

    if (!fp) { fprintf(stderr, "no model\n"); exit(2); }
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%31s", key) != 1) continue;
        if (!strcmp(key, "FACES")) sscanf(line, "%*s %d", &FACES);
        else if (!strcmp(key, "LATCHES")) sscanf(line, "%*s %d", &LATCHES);
        else if (!strcmp(key, "MAXPINS")) sscanf(line, "%*s %d", &MAXPINS);
        else if (!strcmp(key, "PINOK")) {
            sscanf(line, "%*s %d %d %d %d", &a, &b, &c, &d);
            pinok[a][b][c] = d;
        } else if (!strcmp(key, "SPLITONE")) {
            sscanf(line, "%*s %d %d %d", &a, &b, &c);
            splitone[a][b] = c;
        } else if (!strcmp(key, "SPLITTWO")) {
            sscanf(line, "%*s %d %d %d", &a, &b, &c);
            splittwo[a][b] = c;
        } else if (!strcmp(key, "ROT")) {
            sscanf(line, "%*s %d %d", &a, &b);
            rot[a] = b;
        } else if (!strcmp(key, "CODE")) {
            sscanf(line, "%*s %d %d %d", &a, &b, &c);
            codemap[a][b] = c;
        }
    }
    fclose(fp);
}

static int may_split(int lanes, int f, int c)
{
    if (lanes == 1) return splitone[f][c];
    if (lanes == 2) return splittwo[f][c];
    return 0;
}

static void build(void)
{
    int s, a, b, f, c;
    size_t cells = (size_t) (RW + 1) * (RW + 1) * FACES * LATCHES;
    reach = calloc(cells, 1);
    if (!reach) exit(2);

    for (s = 0; s <= 2 * RW; s++) {
        for (a = 0; a <= RW && a <= s; a++) {
            b = s - a;
            if (b < 0 || b > a) continue;
            for (f = 0; f < FACES; f++) {
                for (c = 0; c < LATCHES; c++) {
                    int rows[2], lanes, i, win = 0;
                    rows[0] = a;
                    rows[1] = b;
                    lanes = (a > 0) + (b > 0);
                    for (i = 0; i < 2 && !win; i++) {
                        int n = rows[i], other = rows[1 - i], p;
                        if (n == 0) continue;
                        for (p = 1; p <= MAXPINS && !win; p++) {
                            int rest, nf;
                            if (p > n) break;
                            if (!pinok[f][c][p]) continue;
                            rest = n - p;
                            nf = (f + rot[p]) % FACES;
                            if (!rx(rest, other, nf, codemap[p][0])) { win = 1; break; }
                            if (lanes == 1 && may_split(lanes, f, c) && rest >= 2) {
                                int x, nc = codemap[p][1];
                                for (x = 1; x <= rest - x && !win; x++)
                                    if (!rx(x, rest - x, nf, nc)) win = 1;
                            }
                        }
                    }
                    reach[(((size_t) a * (RW + 1) + b) * FACES + f) * LATCHES + c] = (unsigned char) win;
                }
            }
        }
    }
}

static void find_period(void)
{
    int P, T, n1, n2, f, c, last;
    for (P = 1; P <= 60; P++) {
        last = -1;
        for (n1 = RW - P; n1 >= 0 && last < 0; n1--)
            for (n2 = 0; n2 <= RW && last < 0; n2++)
                for (f = 0; f < FACES && last < 0; f++)
                    for (c = 0; c < LATCHES && last < 0; c++)
                        if (rx(n1, n2, f, c) != rx(n1 + P, n2, f, c)) last = n1;
        T = last + 1;
        if (T + 3 * P <= RW) {
            PER = P;
            PRE = T;
            LIM = (long long) T + 2LL * P;
            return;
        }
    }
    fprintf(stderr, "no period\n");
    exit(2);
}

static int fold(long long n)
{
    if (n <= 0) return 0;
    if (n < PRE) return (int) n;
    return PRE + (int) ((n - PRE) % PER);
}

typedef struct {
    long long rows[2];
    int lanes;
    int face;
    int code;
} Rack;

static void tidy(Rack *r)
{
    long long keep[2];
    int n = 0, i;
    for (i = 0; i < 2; i++)
        if (r->rows[i] > 0) keep[n++] = r->rows[i];
    if (n == 2 && keep[0] < keep[1]) {
        long long t = keep[0];
        keep[0] = keep[1];
        keep[1] = t;
    }
    r->rows[0] = (n > 0) ? keep[0] : 0;
    r->rows[1] = (n > 1) ? keep[1] : 0;
    r->lanes = n;
}

static int value(const Rack *r)
{
    return rx(fold(r->rows[0]), fold(r->rows[1]), r->face, r->code);
}

static void apply(Rack *r, int lane, int pins, long long left)
{
    long long n = r->rows[lane - 1];
    long long rest = n - pins;
    int sp = (left != 0);
    long long other = (r->lanes == 2) ? r->rows[2 - lane] : 0;
    if (sp) {
        r->rows[0] = left;
        r->rows[1] = rest - left;
    } else {
        r->rows[0] = rest;
        r->rows[1] = other;
    }
    r->face = (r->face + rot[pins]) % FACES;
    r->code = codemap[pins][sp ? 1 : 0];
    tidy(r);
}

static int winning_throw(const Rack *r, int *olane, int *opins, long long *oleft)
{
    int i, p;
    int fl = 0, fp = 0;

    for (i = 0; i < r->lanes; i++) {
        long long n = r->rows[i];
        for (p = 1; p <= MAXPINS; p++) {
            Rack nx;
            if (p > n) break;
            if (!pinok[r->face][r->code][p]) continue;
            if (!fl) { fl = i + 1; fp = p; }
            nx = *r;
            apply(&nx, i + 1, p, 0);
            if (!value(&nx)) {
                *olane = i + 1;
                *opins = p;
                *oleft = 0;
                return 1;
            }
            if (r->lanes == 1 && may_split(r->lanes, r->face, r->code) && n - p >= 2) {
                long long rest = n - p, x, top = rest / 2;
                if (top > LIM) top = LIM;
                for (x = 1; x <= top; x++) {
                    nx = *r;
                    apply(&nx, i + 1, p, x);
                    if (!value(&nx)) {
                        *olane = i + 1;
                        *opins = p;
                        *oleft = x;
                        return 1;
                    }
                }
            }
        }
    }
    if (!fl) return 0;
    *olane = fl;
    *opins = fp;
    *oleft = 0;
    return 1;
}

int main(int argc, char **argv)
{
    const char *model = (argc > 1) ? argv[1] : "/app/cabinet_model.txt";
    char line[256];
    Rack r;
    int started = 0;

    setvbuf(stdout, NULL, _IOLBF, 0);
    load_model(model);
    build();
    find_period();
    memset(&r, 0, sizeof(r));

    while (fgets(line, sizeof(line), stdin)) {
        if (!strncmp(line, "BYE", 3) || !strncmp(line, "RESULT", 6)) break;
        if (!strncmp(line, "HOUSE", 5)) continue;
        if (strncmp(line, "RACK", 4)) continue;

        {
            long long n1 = 0, n2 = 0;
            int f = 0, c = 0;
            int got = sscanf(line, "%*s %d %d %lld %lld", &f, &c, &n1, &n2);
            if (got < 3) continue;
            if (got == 3) n2 = 0;
            r.face = f;
            r.code = c;
            r.rows[0] = n1;
            r.rows[1] = n2;
            tidy(&r);
        }

        if (!started) {
            started = 1;
            if (!value(&r)) {
                printf("CALL CONCEDE\n");
                break;
            }
            printf("CALL PLAY\n");
        }

        {
            int lane, pins;
            long long left;
            if (!winning_throw(&r, &lane, &pins, &left)) break;
            printf("THROW %d %d %lld\n", lane, pins, left);
            apply(&r, lane, pins, left);
        }
    }
    return 0;
}
ENTRY_EOF

gcc -O2 -o "$WORK/probe" "$WORK/probe.c"

"$WORK/probe" /app/cabinet/skittle /app/cabinet_model.txt

gcc -O2 -o /app/entry "$WORK/entry.c"
chmod 755 /app/entry

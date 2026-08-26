#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>

#define FACES 5
#define LATCHES 4
#define RW 220
#define PLY_CAP 40
#define REPLY_MS 30000
#define LADDER_LO 1000000000LL
#define LADDER_HI 1000000000000LL

static unsigned char reach[RW + 1][RW + 1][FACES][LATCHES];
static int PER = 0;
static int PRE = 0;
static long long LIM = 0;

static int heavy(int f, int c) { return ((3 * f + 3 * c) % FACES) >= 3; }
static int spread(int f, int c) { return ((3 * f + c) % LATCHES) != 3; }
static int nextface(int f, int p) { return (f + (FACES - p % FACES)) % FACES; }
static int nextcode(int p, int sp) { return (sp ? 2 : 0) + (p == 2 ? 1 : 0); }

static int small_reach(int a, int b, int f, int c)
{
    int t;
    if (a < b) { t = a; a = b; b = t; }
    return reach[a][b][f][c];
}

static void build_table(void)
{
    int s, a, b, f, c;
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
                        for (p = 1; p <= 3 && !win; p++) {
                            int rest, nf;
                            if (p > n) break;
                            if (p == 3 && !heavy(f, c)) continue;
                            rest = n - p;
                            nf = nextface(f, p);
                            if (!small_reach(rest, other, nf, nextcode(p, 0))) { win = 1; break; }
                            if (lanes == 1 && spread(f, c) && rest >= 2) {
                                int x, nc = nextcode(p, 1);
                                for (x = 1; x <= rest - x && !win; x++)
                                    if (!small_reach(x, rest - x, nf, nc)) win = 1;
                            }
                        }
                    }
                    reach[a][b][f][c] = (unsigned char) win;
                }
            }
        }
    }
}

static void derive_period(void)
{
    int P, T, n1, n2, f, c, last;
    for (P = 1; P <= 60; P++) {
        last = -1;
        for (n1 = RW - P; n1 >= 0 && last < 0; n1--)
            for (n2 = 0; n2 <= RW && last < 0; n2++)
                for (f = 0; f < FACES && last < 0; f++)
                    for (c = 0; c < LATCHES && last < 0; c++)
                        if (small_reach(n1, n2, f, c) != small_reach(n1 + P, n2, f, c)) last = n1;
        T = last + 1;
        if (T + 3 * P <= RW) {
            PER = P;
            PRE = T;
            LIM = (long long) T + 2LL * P;
            return;
        }
    }
    fprintf(stderr, "referee: no period\n");
    exit(2);
}

static int fold(long long n)
{
    if (n < 0) return 0;
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
    return small_reach(fold(r->rows[0]), fold(r->rows[1]), r->face, r->code);
}

static int legal(const Rack *r, int lane, int pins, long long left)
{
    long long n, rest;
    if (lane < 1 || lane > r->lanes) return 0;
    if (pins < 1 || pins > 3) return 0;
    n = r->rows[lane - 1];
    if (pins > n) return 0;
    if (pins == 3 && !heavy(r->face, r->code)) return 0;
    rest = n - pins;
    if (left == 0) return 1;
    if (r->lanes != 1) return 0;
    if (!spread(r->face, r->code)) return 0;
    if (rest < 2) return 0;
    if (left < 1 || left > rest - 1) return 0;
    return 1;
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
    r->face = nextface(r->face, pins);
    r->code = nextcode(pins, sp);
    tidy(r);
}

static int pick(const Rack *r, int *olane, int *opins, long long *oleft)
{
    int i, p;
    int fl = 0, fp = 0;
    long long fx = 0;

    for (i = 0; i < r->lanes; i++) {
        long long n = r->rows[i];
        for (p = 1; p <= 3; p++) {
            Rack nx;
            if (p > n) break;
            if (p == 3 && !heavy(r->face, r->code)) continue;
            if (!fl) { fl = i + 1; fp = p; fx = 0; }
            nx = *r;
            apply(&nx, i + 1, p, 0);
            if (!value(&nx)) {
                *olane = i + 1;
                *opins = p;
                *oleft = 0;
                return 1;
            }
            if (r->lanes == 1 && spread(r->face, r->code) && n - p >= 2) {
                long long rest = n - p, x;
                long long top = rest / 2;
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
    *oleft = fx;
    return 1;
}

static unsigned long long sm_state;
static unsigned long long sm_next(void)
{
    unsigned long long z = (sm_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}
static long long rng_range(long long lo, long long hi)
{
    return lo + (long long) (sm_next() % (unsigned long long) (hi - lo + 1));
}

static int child_in, child_out;
static pid_t child_pid;
static char rbuf[8192];
static int rlen, rpos;

static int spawn_entry(const char *path)
{
    int a[2], b[2];
    if (pipe(a) || pipe(b)) return 0;
    child_pid = fork();
    if (child_pid < 0) return 0;
    if (child_pid == 0) {
        dup2(a[0], 0);
        dup2(b[1], 1);
        close(a[0]); close(a[1]); close(b[0]); close(b[1]);
        execl(path, path, (char *) NULL);
        _exit(127);
    }
    close(a[0]);
    close(b[1]);
    child_in = a[1];
    child_out = b[0];
    rlen = rpos = 0;
    return 1;
}

static void reap_entry(void)
{
    int st;
    close(child_in);
    close(child_out);
    kill(child_pid, SIGKILL);
    waitpid(child_pid, &st, 0);
}

static int read_line(char *dst, int cap)
{
    int n = 0;
    for (;;) {
        while (rpos < rlen) {
            char ch = rbuf[rpos++];
            if (ch == '\n') { dst[n] = 0; return 1; }
            if (n < cap - 1) dst[n++] = ch;
        }
        {
            struct pollfd pf;
            int pr;
            pf.fd = child_out;
            pf.events = POLLIN;
            pr = poll(&pf, 1, REPLY_MS);
            if (pr <= 0) return 0;
            rlen = (int) read(child_out, rbuf, sizeof(rbuf));
            rpos = 0;
            if (rlen <= 0) return 0;
        }
    }
}

static void send_rack(const Rack *r)
{
    char buf[128];
    int n;
    if (r->lanes == 1)
        n = snprintf(buf, sizeof(buf), "RACK %d %d %lld\n", r->face, r->code, r->rows[0]);
    else
        n = snprintf(buf, sizeof(buf), "RACK %d %d %lld %lld\n", r->face, r->code, r->rows[0], r->rows[1]);
    if (write(child_in, buf, n) != n) { /* entry gone; read_line will time out */ }
}

static void send_line(const char *s)
{
    size_t n = strlen(s);
    if (write(child_in, s, n) != n) { /* entry gone */ }
}

typedef struct {
    const char *tier;
    Rack start;
    int truth;
    int called;
    int call_ok;
    int won;
    int foul;
    int died;
} Report;

static void run_match(const char *entry, Report *rep)
{
    char line[256];
    Rack r = rep->start;
    int ply;

    rep->truth = value(&r);
    rep->called = -1;
    rep->call_ok = 0;
    rep->won = 0;
    rep->foul = 0;
    rep->died = 0;

    if (!spawn_entry(entry)) { rep->died = 1; return; }
    send_rack(&r);

    if (!read_line(line, sizeof(line))) { rep->died = 1; reap_entry(); return; }
    if (strncmp(line, "CALL PLAY", 9) == 0) rep->called = 1;
    else if (strncmp(line, "CALL CONCEDE", 12) == 0) rep->called = 0;
    else { rep->died = 1; reap_entry(); return; }

    rep->call_ok = (rep->called == rep->truth);

    if (rep->called == 0) {
        send_line("BYE\n");
        reap_entry();
        rep->won = rep->call_ok;
        return;
    }

    if (!rep->call_ok) {
        send_line("BYE\n");
        reap_entry();
        return;
    }

    for (ply = 0; ply < PLY_CAP; ply++) {
        int lane, pins, got;
        long long left;
        int hl, hp;
        long long hx;

        if (!read_line(line, sizeof(line))) { rep->died = 1; reap_entry(); return; }
        got = sscanf(line, "THROW %d %d %lld", &lane, &pins, &left);
        if (got < 2) { rep->foul = 1; reap_entry(); return; }
        if (got == 2) left = 0;
        if (!legal(&r, lane, pins, left)) { rep->foul = 1; reap_entry(); return; }
        apply(&r, lane, pins, left);

        if (r.lanes == 0) {
            send_line("RESULT PLAYER\nBYE\n");
            reap_entry();
            rep->won = 1;
            return;
        }
        if (value(&r)) { reap_entry(); return; }

        if (!pick(&r, &hl, &hp, &hx)) {
            send_line("RESULT PLAYER\nBYE\n");
            reap_entry();
            rep->won = 1;
            return;
        }
        apply(&r, hl, hp, hx);
        {
            char out[160];
            snprintf(out, sizeof(out), "HOUSE %d %d %lld\n", hl, hp, hx);
            send_line(out);
        }
        if (r.lanes == 0) {
            send_line("RESULT HOUSE\nBYE\n");
            reap_entry();
            return;
        }
        send_rack(&r);
    }

    reap_entry();
    rep->won = 1;
}

static void deal(Report *rep, const char *tier, long long lo, long long hi, int force_two, int home)
{
    Rack r;
    memset(&r, 0, sizeof(r));
    r.rows[0] = rng_range(lo, hi);
    if (force_two || (sm_next() & 1))
        r.rows[1] = rng_range(lo, hi);
    else
        r.rows[1] = 0;
    if (home) {
        r.face = 0;
        r.code = 0;
    } else {
        r.face = (int) rng_range(0, FACES - 1);
        r.code = (int) rng_range(0, LATCHES - 1);
    }
    tidy(&r);
    rep->tier = tier;
    rep->start = r;
}

int main(int argc, char **argv)
{
    const char *entry = (argc > 1) ? argv[1] : "/app/entry";
    unsigned long long seed = (argc > 2) ? strtoull(argv[2], NULL, 10) : 20260712ULL;
    Report reps[128];
    int n = 0, i;

    signal(SIGPIPE, SIG_IGN);
    build_table();
    derive_period();
    sm_state = seed;

    for (i = 0; i < 30; i++) {
        Rack r;
        memset(&r, 0, sizeof(r));
        do {
            r.rows[0] = rng_range(3, 30);
            r.rows[1] = (sm_next() & 1) ? rng_range(1, 10) : 0;
        } while (r.rows[0] + r.rows[1] > 40);
        r.face = (int) rng_range(0, FACES - 1);
        r.code = (int) rng_range(0, LATCHES - 1);
        tidy(&r);
        reps[n].tier = "band";
        reps[n].start = r;
        n++;
    }
    for (i = 0; i < 30; i++) {
        deal(&reps[n], "coupled", 60, 400, 1, 0);
        n++;
    }
    for (i = 0; i < 30; i++) {
        deal(&reps[n], "ladder", LADDER_LO, LADDER_HI, 0, 0);
        n++;
    }

    for (i = 0; i < n; i++)
        run_match(entry, &reps[i]);

    printf("{\"period\":%d,\"preperiod\":%d,\"boards\":[", PER, PRE);
    for (i = 0; i < n; i++) {
        Report *r = &reps[i];
        printf("%s{\"tier\":\"%s\",\"face\":%d,\"code\":%d,\"lanes\":%d,\"r1\":%lld,\"r2\":%lld,"
               "\"truth\":\"%s\",\"call\":\"%s\",\"call_ok\":%s,\"won\":%s,\"foul\":%s,\"died\":%s}",
               i ? "," : "", r->tier, r->start.face, r->start.code, r->start.lanes,
               r->start.rows[0], r->start.rows[1],
               r->truth ? "PLAY" : "CONCEDE",
               r->called == 1 ? "PLAY" : (r->called == 0 ? "CONCEDE" : "NONE"),
               r->call_ok ? "true" : "false",
               r->won ? "true" : "false",
               r->foul ? "true" : "false",
               r->died ? "true" : "false");
    }
    printf("]}\n");
    return 0;
}

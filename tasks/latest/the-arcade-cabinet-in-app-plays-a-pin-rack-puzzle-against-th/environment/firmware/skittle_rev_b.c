#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rack.h"

static unsigned char reach[WMAX][WMAX][FACES][LATCHES];

int heavy_ball_armed(int face, int code)
{
    return ((3 * face + 3 * code) % FACES) >= 3;
}

int spread_armed(int face, int code)
{
    return ((3 * face + code) % LATCHES) != 3;
}

int advance_face(int face, int pins)
{
    return (face + (FACES - pins % FACES)) % FACES;
}

int filed_code(int pins, int spread)
{
    return (spread ? 2 : 0) + (pins == 2 ? 1 : 0);
}

static int reach_of(int a, int b, int face, int code)
{
    int t;
    if (a < b) { t = a; a = b; b = t; }
    return reach[a][b][face][code];
}

void spin_up(void)
{
    int s, a, b, face, code;

    for (s = 0; s <= 2 * BAND; s++) {
        for (a = 0; a <= BAND && a <= s; a++) {
            b = s - a;
            if (b < 0 || b > a) continue;
            for (face = 0; face < FACES; face++) {
                for (code = 0; code < LATCHES; code++) {
                    int rows[2];
                    int lanes, i, hit = 0;

                    rows[0] = a;
                    rows[1] = b;
                    lanes = (a > 0) + (b > 0);

                    for (i = 0; i < 2 && !hit; i++) {
                        int n = rows[i];
                        int other = rows[1 - i];
                        int pins;
                        if (n == 0) continue;
                        for (pins = 1; pins <= 3 && !hit; pins++) {
                            int rest, nf;
                            if (pins > n) break;
                            if (pins == 3 && !heavy_ball_armed(face, code)) continue;
                            rest = n - pins;
                            nf = advance_face(face, pins);
                            if (!reach_of(rest, other, nf, filed_code(pins, 0))) {
                                hit = 1;
                                break;
                            }
                            if (lanes == 1 && spread_armed(face, code) && rest >= 2) {
                                int x;
                                int nc = filed_code(pins, 1);
                                for (x = 1; x <= rest - x && !hit; x++)
                                    if (!reach_of(x, rest - x, nf, nc)) hit = 1;
                            }
                        }
                    }
                    reach[a][b][face][code] = (unsigned char) hit;
                }
            }
        }
    }
}

static Rack rk;

void normalise(Rack *r)
{
    int keep[2];
    int n = 0, i;
    for (i = 0; i < 2; i++)
        if (r->rows[i] > 0) keep[n++] = r->rows[i];
    if (n == 2 && keep[0] < keep[1]) {
        int t = keep[0];
        keep[0] = keep[1];
        keep[1] = t;
    }
    r->rows[0] = (n > 0) ? keep[0] : 0;
    r->rows[1] = (n > 1) ? keep[1] : 0;
    r->lanes = n;
}

int throw_legal(const Rack *r, int lane, int pins, int left)
{
    int n, rest;
    if (lane < 1 || lane > r->lanes) return 0;
    if (pins < 1 || pins > 3) return 0;
    n = r->rows[lane - 1];
    if (pins > n) return 0;
    if (pins == 3 && !heavy_ball_armed(r->face, r->code)) return 0;
    rest = n - pins;
    if (left == 0) return 1;
    if (r->lanes != 1) return 0;
    if (!spread_armed(r->face, r->code)) return 0;
    if (rest < 2) return 0;
    if (left < 1 || left > rest - 1) return 0;
    return 1;
}

void throw_apply(Rack *r, int lane, int pins, int left)
{
    int n = r->rows[lane - 1];
    int rest = n - pins;
    int spread = (left != 0);
    int other = (r->lanes == 2) ? r->rows[2 - lane] : 0;

    if (spread) {
        r->rows[0] = left;
        r->rows[1] = rest - left;
    } else {
        r->rows[0] = rest;
        r->rows[1] = other;
    }
    r->face = advance_face(r->face, pins);
    r->code = filed_code(pins, spread);
    normalise(r);
}

int house_pick(const Rack *r, int *lane, int *pins, int *left)
{
    int i, p, x;
    int fb_lane = 0, fb_pins = 0, fb_left = 0;

    for (i = 0; i < r->lanes; i++) {
        int n = r->rows[i];
        int other = (r->lanes == 2) ? r->rows[1 - i] : 0;
        for (p = 1; p <= 3; p++) {
            int rest, nf;
            if (p > n) break;
            if (p == 3 && !heavy_ball_armed(r->face, r->code)) continue;
            rest = n - p;
            nf = advance_face(r->face, p);
            if (!fb_lane) { fb_lane = i + 1; fb_pins = p; fb_left = 0; }
            if (!reach_of(rest, other, nf, filed_code(p, 0))) {
                *lane = i + 1;
                *pins = p;
                *left = 0;
                return 1;
            }
            if (r->lanes == 1 && spread_armed(r->face, r->code) && rest >= 2) {
                int nc = filed_code(p, 1);
                for (x = 1; x <= rest - x; x++) {
                    if (!reach_of(x, rest - x, nf, nc)) {
                        *lane = i + 1;
                        *pins = p;
                        *left = x;
                        return 1;
                    }
                }
            }
        }
    }
    if (!fb_lane) return 0;
    *lane = fb_lane;
    *pins = fb_pins;
    *left = fb_left;
    return 1;
}

static void print_rack(const char *tag, const Rack *r)
{
    if (r->lanes == 0)
        printf("%s %d %d 0\n", tag, r->face, r->code);
    else if (r->lanes == 1)
        printf("%s %d %d 1 %d\n", tag, r->face, r->code, r->rows[0]);
    else
        printf("%s %d %d 2 %d %d\n", tag, r->face, r->code, r->rows[0], r->rows[1]);
}

static int house_turn(void)
{
    int lane, pins, left;
    if (!house_pick(&rk, &lane, &pins, &left)) {
        printf("RESULT PLAYER\n");
        rk.live = 0;
        return 1;
    }
    throw_apply(&rk, lane, pins, left);
    printf("HOUSE %d %d %d\n", lane, pins, left);
    print_rack("RACK", &rk);
    if (rk.lanes == 0) {
        printf("RESULT HOUSE\n");
        rk.live = 0;
    }
    return 1;
}

int main(void)
{
    char line[256];

    setvbuf(stdout, NULL, _IOLBF, 0);
    spin_up();
    rk.live = 0;

    while (fgets(line, sizeof(line), stdin)) {
        char verb[32];
        int a1, a2, a3, got;

        if (sscanf(line, "%31s", verb) != 1) continue;

        if (strcmp(verb, "QUIT") == 0) break;

        if (strcmp(verb, "RACK") == 0) {
            int n1 = 0, n2 = 0;
            got = sscanf(line, "%*s %d %d %d %d", &a1, &a2, &n1, &n2);
            if (got < 3) { printf("REFUSED ARGS\nEND\n"); continue; }
            if (a1 < 0 || a1 >= FACES || a2 < 0 || a2 >= LATCHES) { printf("REFUSED ARGS\nEND\n"); continue; }
            if (n1 < 1 || (got == 4 && n2 < 1)) { printf("REFUSED ARGS\nEND\n"); continue; }
            if (got == 3) n2 = 0;
            if (n1 + n2 > BAND || n1 > BAND || n2 > BAND) { printf("REFUSED BAND\nEND\n"); continue; }
            rk.face = a1;
            rk.code = a2;
            rk.rows[0] = n1;
            rk.rows[1] = n2;
            normalise(&rk);
            rk.live = 1;
            print_rack("READY", &rk);
            printf("END\n");
            continue;
        }

        if (!rk.live) { printf("REFUSED IDLE\nEND\n"); continue; }

        if (strcmp(verb, "SHOW") == 0) {
            print_rack("RACK", &rk);
            printf("END\n");
            continue;
        }

        if (strcmp(verb, "HOUSE") == 0) {
            house_turn();
            printf("END\n");
            continue;
        }

        if (strcmp(verb, "THROW") == 0) {
            got = sscanf(line, "%*s %d %d %d", &a1, &a2, &a3);
            if (got < 2) { printf("REFUSED ARGS\nEND\n"); continue; }
            if (got == 2) a3 = 0;
            if (!throw_legal(&rk, a1, a2, a3)) { printf("REJECT\nEND\n"); continue; }
            throw_apply(&rk, a1, a2, a3);
            print_rack("OK", &rk);
            if (rk.lanes == 0) {
                printf("RESULT PLAYER\n");
                rk.live = 0;
                printf("END\n");
                continue;
            }
            house_turn();
            printf("END\n");
            continue;
        }

        printf("REFUSED ARGS\nEND\n");
    }
    return 0;
}

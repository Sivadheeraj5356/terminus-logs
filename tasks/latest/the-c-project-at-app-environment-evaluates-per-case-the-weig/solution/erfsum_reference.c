#include "erfsum.h"

#include <math.h>
#include <stdint.h>
#include <string.h>

/*
 * Reference oracle for S = sum_i c_i * erf(x_i), erf the error function. The
 * terms nearly cancel to hundreds of digits, so both c_i and x_i are parsed from
 * their full-precision decimal strings and the whole computation runs in a
 * from-scratch binary big-float with a wide significand and an unbounded
 * exponent.
 */

#define NLIMB 208                /* 208 * 32-bit limbs = 6656-bit significand */
#define WBITS (32 * NLIMB)

/* value = sign * M * 2^e, M little-endian in d[] (d[0] least significant),
 * normalized so bit WBITS-1 of M is set, or sign == 0 for zero. */
typedef struct { int sign; long e; uint32_t d[NLIMB]; } bf;

static int clz32(uint32_t x) {
    int n = 0;
    while (!(x & 0x80000000u)) { x <<= 1; n++; }
    return n;
}

/* index (from LSB, 0-based) of the highest set bit of a little-endian array */
static long hibit(const uint32_t *w, int L) {
    for (int i = L - 1; i >= 0; i--) {
        if (w[i]) return (long)i * 32 + (31 - clz32(w[i]));
    }
    return -1;
}

/* dst[0..Ld-1] = (src[0..Ls-1] << s), little-endian, low Ld limbs kept */
static void shl_wide(uint32_t *dst, int Ld, const uint32_t *src, int Ls, long s) {
    long ls = s / 32, bs = s % 32;
    for (int i = 0; i < Ld; i++) dst[i] = 0;
    for (int i = 0; i < Ld; i++) {
        long j = (long)i - ls;
        uint32_t lo = (j >= 0 && j < Ls) ? src[j] : 0;
        uint32_t hi = (bs && j - 1 >= 0 && j - 1 < Ls) ? src[j - 1] : 0;
        dst[i] = bs ? (uint32_t)((lo << bs) | (hi >> (32 - bs))) : lo;
    }
}

/* dst[0..Ld-1] = (src[0..Ls-1] >> s), little-endian */
static void shr_wide(uint32_t *dst, int Ld, const uint32_t *src, int Ls, long s) {
    long ls = s / 32, bs = s % 32;
    for (int i = 0; i < Ld; i++) {
        long j = (long)i + ls;
        uint32_t lo = (j < Ls) ? src[j] : 0;
        uint32_t hi = (bs && j + 1 < Ls) ? src[j + 1] : 0;
        dst[i] = bs ? (uint32_t)((lo >> bs) | (hi << (32 - bs))) : lo;
    }
}

static int cmp_mag(const uint32_t *a, const uint32_t *b, int L) {
    for (int i = L - 1; i >= 0; i--) {
        if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
    }
    return 0;
}

static void add_mag(uint32_t *r, const uint32_t *a, const uint32_t *b, int L) {
    uint64_t c = 0;
    for (int i = 0; i < L; i++) {
        uint64_t s = (uint64_t)a[i] + b[i] + c;
        r[i] = (uint32_t)s;
        c = s >> 32;
    }
}

/* r = a - b, requires a >= b */
static void sub_mag(uint32_t *r, const uint32_t *a, const uint32_t *b, int L) {
    int64_t borrow = 0;
    for (int i = 0; i < L; i++) {
        int64_t s = (int64_t)a[i] - b[i] - borrow;
        if (s < 0) { s += ((int64_t)1 << 32); borrow = 1; } else borrow = 0;
        r[i] = (uint32_t)s;
    }
}

static void set_zero(bf *r) { r->sign = 0; r->e = 0; memset(r->d, 0, sizeof(r->d)); }

/* pack a wide little-endian magnitude (value = sign * W * 2^e_lsb) into a bf */
static void pack(bf *r, const uint32_t *w, int Lw, long e_lsb, int sign) {
    long hb = hibit(w, Lw);
    if (hb < 0) { set_zero(r); return; }
    long drop = hb + 1 - WBITS;
    if (drop >= 0) shr_wide(r->d, NLIMB, w, Lw, drop);
    else shl_wide(r->d, NLIMB, w, Lw, -drop);
    r->e = e_lsb + drop;
    r->sign = sign;
}

static void bf_from_u64(bf *r, uint64_t v, long e, int sign) {
    uint32_t w[2] = { (uint32_t)v, (uint32_t)(v >> 32) };
    if (v == 0) { set_zero(r); return; }
    pack(r, w, 2, e, sign);
}

static bf bf_from_double(double x) {
    bf r;
    if (x == 0.0) { set_zero(&r); return r; }
    int sign = x < 0 ? -1 : 1;
    x = fabs(x);
    int E;
    double f = frexp(x, &E);            /* x = f * 2^E, f in [0.5,1) */
    uint64_t I = (uint64_t)ldexp(f, 53);
    bf_from_u64(&r, I, (long)E - 53, sign);
    return r;
}

static uint64_t top64(const bf *a) {
    return ((uint64_t)a->d[NLIMB - 1] << 32) | a->d[NLIMB - 2];
}

static double bf_to_double(const bf *a) {
    if (a->sign == 0) return 0.0;
    return a->sign * ldexp((double)top64(a), a->e + (WBITS - 64));
}

static bf bf_neg(bf a) { a.sign = -a.sign; return a; }

static bf bf_add(bf a, bf b) {
    bf r;
    if (a.sign == 0) return b;
    if (b.sign == 0) return a;
    /* If the exponents differ by a full significand width, the smaller operand
     * sits entirely below the least significant bit kept here, so it cannot
     * affect the rounded result; dropping it also bounds the alignment shift
     * below to WBITS-1, which keeps every shifted value inside the wide buffer. */
    if (a.e - b.e >= WBITS) return a;
    if (b.e - a.e >= WBITS) return b;
    long lo = a.e < b.e ? a.e : b.e;
    uint32_t Aw[2 * NLIMB], Bw[2 * NLIMB], Sw[2 * NLIMB];
    shl_wide(Aw, 2 * NLIMB, a.d, NLIMB, a.e - lo);
    shl_wide(Bw, 2 * NLIMB, b.d, NLIMB, b.e - lo);
    if (a.sign == b.sign) {
        add_mag(Sw, Aw, Bw, 2 * NLIMB);
        pack(&r, Sw, 2 * NLIMB, lo, a.sign);
    } else {
        int c = cmp_mag(Aw, Bw, 2 * NLIMB);
        if (c == 0) { set_zero(&r); return r; }
        if (c > 0) { sub_mag(Sw, Aw, Bw, 2 * NLIMB); pack(&r, Sw, 2 * NLIMB, lo, a.sign); }
        else { sub_mag(Sw, Bw, Aw, 2 * NLIMB); pack(&r, Sw, 2 * NLIMB, lo, b.sign); }
    }
    return r;
}

static bf bf_sub(bf a, bf b) { return bf_add(a, bf_neg(b)); }

static bf bf_mul(bf a, bf b) {
    bf r;
    if (a.sign == 0 || b.sign == 0) { set_zero(&r); return r; }
    uint32_t P[2 * NLIMB];
    memset(P, 0, sizeof(P));
    for (int i = 0; i < NLIMB; i++) {
        uint64_t c = 0;
        uint64_t ai = a.d[i];
        for (int j = 0; j < NLIMB; j++) {
            uint64_t cur = (uint64_t)P[i + j] + ai * b.d[j] + c;
            P[i + j] = (uint32_t)cur;
            c = cur >> 32;
        }
        P[i + NLIMB] += (uint32_t)c;
    }
    pack(&r, P, 2 * NLIMB, a.e + b.e, a.sign * b.sign);
    return r;
}

static bf bf_mul_si(bf a, long k) {
    bf r;
    if (a.sign == 0 || k == 0) { set_zero(&r); return r; }
    int sk = k < 0 ? -1 : 1;
    uint64_t kk = k < 0 ? (uint64_t)(-k) : (uint64_t)k;
    uint32_t P[NLIMB + 2];
    memset(P, 0, sizeof(P));
    uint64_t c = 0;
    for (int i = 0; i < NLIMB; i++) {
        uint64_t cur = (uint64_t)a.d[i] * kk + c;
        P[i] = (uint32_t)cur;
        c = cur >> 32;
    }
    P[NLIMB] = (uint32_t)c;
    P[NLIMB + 1] = (uint32_t)(c >> 32);
    pack(&r, P, NLIMB + 2, a.e, a.sign * sk);
    return r;
}

/* 1/a, exponent handled without overflowing the seed */
static bf bf_recip(bf a) {
    double md = (double)top64(&a);              /* in [2^63, 2^64) */
    bf y = bf_from_double(1.0 / md);
    y.e += -(a.e + (WBITS - 64));
    bf two = bf_from_double(2.0);
    for (int it = 0; it < 8; it++) {
        bf ay = bf_mul(a, y);
        bf t = bf_sub(two, ay);
        y = bf_mul(y, t);
    }
    return y;
}

static bf bf_div(bf a, bf b) { return bf_mul(a, bf_recip(b)); }

/* a / k for a small positive integer k, by long division of the significand
 * with 32 guard bits so no precision is lost; used in the erf series loop where
 * a full Newton reciprocal per step would dominate the run time. */
static bf bf_div_si(bf a, uint32_t k) {
    bf r;
    if (a.sign == 0 || k == 0) { set_zero(&r); return r; }
    uint32_t num[NLIMB + 1];
    num[0] = 0;
    for (int i = 0; i < NLIMB; i++) num[i + 1] = a.d[i];   /* M << 32 */
    uint32_t q[NLIMB + 1];
    uint64_t rem = 0;
    for (int i = NLIMB; i >= 0; i--) {
        uint64_t cur = (rem << 32) | num[i];
        q[i] = (uint32_t)(cur / k);
        rem = cur % k;
    }
    pack(&r, q, NLIMB + 1, a.e - 32, a.sign);
    return r;
}

/* parse a plain decimal literal (optional sign, digits, one '.') to a bf */
static bf parse_bf(const char *s) {
    int sign = 1;
    if (*s == '+') s++;
    else if (*s == '-') { sign = -1; s++; }
    bf acc = bf_from_double(0.0);
    long frac = 0;
    int seen_dot = 0;
    for (; *s; s++) {
        if (*s == '.') { seen_dot = 1; continue; }
        if (*s < '0' || *s > '9') continue;
        acc = bf_add(bf_mul_si(acc, 10), bf_from_double((double)(*s - '0')));
        if (seen_dot) frac++;
    }
    if (frac) {
        bf pten = bf_from_double(1.0);
        for (long i = 0; i < frac; i++) pten = bf_mul_si(pten, 10);
        acc = bf_div(acc, pten);
    }
    acc.sign *= sign;
    return acc;
}

/* 2/sqrt(pi) to ~2010 fractional digits, parsed straight into a big-float and
 * folded onto the accumulated series sum so the erf prefactor carries full
 * precision rather than a rounded double. */
static const char *const TWO_OVER_SQRT_PI =
    "1."
    "1283791670955125738961589031215451716881012586579977136881714434212849"
    "3688298682897348732040421472688605669581272341470337986298965232573273"
    "0979040035537986585675274119196879520704928700435945142423160491545640"
    "4411090170543464332444169266162227990255269089720461364753818374903174"
    "9323170260213279671554399875466832071559775233348815246607876043270120"
    "3287243392470100916625063893758913312576651631043248869097731406379754"
    "8617635563658967789502170018369170684432635651786705036660240492451244"
    "4744989454006779486252859931885270085660898072663160787539197121631867"
    "5658441114765847576463158466211523929554936506180343123616119044459235"
    "2649307180801706885897250057894784328362385486195484511397575915580997"
    "4963827387447938414572126684953593989721917752608726745291175750308616"
    "1868839476966576982758350723791327018482697850617660789930811682114508"
    "2965496469503494840187939766833554297711783356674789971831633002753719"
    "7737240879282581457385792761475465346223685735760423104973243794381779"
    "3615062990240294910543518259630544244126468693514830520512369964555789"
    "9739050603338993937132772461844088497228662621222034794086331088707292"
    "3260053362177860954410826054966428673172942058370989816767753849539274"
    "8117508206316946634152433906289780994634796224277050525789933163762144"
    "9446100346112001461110147605381404784186502587303713088160546060912171"
    "1778663730517261051766944196218323045110268032689619215468125813530418"
    "4955488915831319872573827621301394798442321270036762403269655890511176"
    "0917943905598061845977122310912563948886446368189790964513978463786936"
    "4073400641245842006487912585143705083809115767366267119261145776029734"
    "6542852808312236531894105842976564219243112231755769151738741538633137"
    "9514660726612116160853553108577744936791730762563835088920082338519646"
    "4140202975955197479331048240246204171194516154832646487303937411587437"
    "3991373282632741414920329349124653295705526587225112073460916295019351"
    "6738517635502050323435831770870226388995590226041289314884709283396957"
    "96081675002149402705503760956452458569391936454552087427059";

/* The error-function power series without the 2/sqrt(pi) prefactor: sum_{n>=0}
 * (-1)^n x^(2n+1) / (n! (2n+1)), with x parsed straight from its full-precision
 * decimal string; using only its double value would perturb the argument, which
 * the cancellation later amplifies past the tolerance. Using b_n = (-1)^n
 * x^(2n+1)/n! from the recurrence b_0 = x, b_n = b_{n-1} * (-x^2) / n, each term
 * added to the sum is b_n / (2n+1), run until it underflows below the working
 * significand. The 2/sqrt(pi) factor is applied once to the whole accumulated
 * weighted sum in erfsum_weighted_sum. */
static bf erf_series_bf(const char *xs) {
    bf x = parse_bf(xs);
    bf x2 = bf_mul(x, x);
    bf b = x;
    bf sum = x;                          /* n = 0 term: b_0 / 1 = x */
    for (int n = 1; n < 20000; n++) {
        b = bf_mul(b, x2);
        b.sign = -b.sign;                /* * (-1) */
        b = bf_div_si(b, (uint32_t)n);   /* / n  -> b_n */
        bf term = bf_div_si(b, (uint32_t)(2 * n + 1));
        sum = bf_add(sum, term);
        if (term.sign == 0) break;
        if (sum.sign != 0 && term.e < sum.e - (WBITS + 8)) break;
    }
    return sum;
}

void erfsum_weighted_sum(int n, const char *const *c, const char *const *x, double *out) {
    bf S = bf_from_double(0.0);
    for (int i = 0; i < n; i++) {
        bf term = bf_mul(parse_bf(c[i]), erf_series_bf(x[i]));
        S = bf_add(S, term);
    }
    S = bf_mul(S, parse_bf(TWO_OVER_SQRT_PI));
    out[0] = bf_to_double(&S);
}

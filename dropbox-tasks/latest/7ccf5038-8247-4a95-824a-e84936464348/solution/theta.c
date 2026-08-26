#include "theta.h"

#include <math.h>
#include <stdint.h>
#include <string.h>

#define L 80
#define BITS (32 * L)
#define CONV (BITS + 24)

typedef struct {
    int sign;
    int64_t e;
    uint32_t m[L];
} bf;

static void bf_zero(bf *a) {
    a->sign = 0;
    a->e = 0;
    memset(a->m, 0, sizeof(a->m));
}

static int bf_is_zero(const bf *a) { return a->sign == 0; }

static int clz_field(const uint32_t *m, int n) {
    int c = 0;
    for (int i = 0; i < n; i++) {
        if (m[i] == 0) {
            c += 32;
            continue;
        }
        uint32_t v = m[i];
        int lz = 0;
        while (!(v & 0x80000000u)) {
            v <<= 1;
            lz++;
        }
        return c + lz;
    }
    return 32 * n;
}

static void shl_field(uint32_t *m, int n, int s) {
    if (s <= 0) return;
    int limb = s / 32, bit = s % 32;
    if (limb) {
        for (int i = 0; i < n; i++) {
            int j = i + limb;
            m[i] = (j < n) ? m[j] : 0;
        }
    }
    if (bit) {
        for (int i = 0; i < n; i++) {
            uint32_t hi = m[i] << bit;
            uint32_t lo = (i + 1 < n) ? (m[i + 1] >> (32 - bit)) : 0;
            m[i] = hi | lo;
        }
    }
}

static void shr_field(uint32_t *m, int n, int s) {
    if (s <= 0) return;
    int limb = s / 32, bit = s % 32;
    if (limb) {
        for (int i = n - 1; i >= 0; i--) {
            int j = i - limb;
            m[i] = (j >= 0) ? m[j] : 0;
        }
    }
    if (bit) {
        for (int i = n - 1; i >= 0; i--) {
            uint32_t lo = m[i] >> bit;
            uint32_t hi = (i - 1 >= 0) ? (m[i - 1] << (32 - bit)) : 0;
            m[i] = hi | lo;
        }
    }
}

static void bf_normalize(bf *a) {
    int lz = clz_field(a->m, L);
    if (lz >= BITS) {
        bf_zero(a);
        return;
    }
    if (lz > 0) {
        shl_field(a->m, L, lz);
        a->e -= lz;
    }
}

static void bf_set_double(bf *r, double d) {
    bf_zero(r);
    if (d == 0.0) return;
    int s = 1;
    if (d < 0) {
        s = -1;
        d = -d;
    }
    int ke;
    double mf = frexp(d, &ke);
    uint64_t mi = (uint64_t)ldexp(mf, 53);
    r->sign = s;
    r->m[0] = (uint32_t)(mi >> 32);
    r->m[1] = (uint32_t)mi;
    r->e = ke + 10;
    bf_normalize(r);
}

static int mant_cmp(const uint32_t *a, const uint32_t *b) {
    for (int i = 0; i < L; i++) {
        if (a[i] < b[i]) return -1;
        if (a[i] > b[i]) return 1;
    }
    return 0;
}

static int mant_add(uint32_t *r, const uint32_t *a, const uint32_t *b) {
    uint64_t carry = 0;
    for (int i = L - 1; i >= 0; i--) {
        uint64_t s = (uint64_t)a[i] + b[i] + carry;
        r[i] = (uint32_t)s;
        carry = s >> 32;
    }
    return (int)carry;
}

static void mant_sub(uint32_t *r, const uint32_t *a, const uint32_t *b) {
    int64_t borrow = 0;
    for (int i = L - 1; i >= 0; i--) {
        int64_t s = (int64_t)a[i] - b[i] - borrow;
        if (s < 0) {
            s += ((int64_t)1 << 32);
            borrow = 1;
        } else {
            borrow = 0;
        }
        r[i] = (uint32_t)s;
    }
}

static void bf_copy(bf *d, const bf *s) { *d = *s; }

static void bf_scale2(bf *a, int64_t k) {
    if (bf_is_zero(a)) return;
    a->e += k;
}

static void bf_add(bf *r, const bf *a, const bf *b) {
    if (bf_is_zero(a)) {
        bf_copy(r, b);
        return;
    }
    if (bf_is_zero(b)) {
        bf_copy(r, a);
        return;
    }
    bf A = *a, B = *b;
    int64_t ea = A.e, eb = B.e;
    if (ea < eb) {
        int64_t d = eb - ea;
        if (d >= BITS) {
            bf_copy(r, b);
            return;
        }
        shr_field(A.m, L, (int)d);
        A.e = eb;
    } else if (eb < ea) {
        int64_t d = ea - eb;
        if (d >= BITS) {
            bf_copy(r, a);
            return;
        }
        shr_field(B.m, L, (int)d);
        B.e = ea;
    }
    if (A.sign == B.sign) {
        uint32_t tmp[L];
        int carry = mant_add(tmp, A.m, B.m);
        r->sign = A.sign;
        r->e = A.e;
        memcpy(r->m, tmp, sizeof(tmp));
        if (carry) {
            shr_field(r->m, L, 1);
            r->m[0] |= 0x80000000u;
            r->e += 1;
        }
        bf_normalize(r);
    } else {
        int c = mant_cmp(A.m, B.m);
        if (c == 0) {
            bf_zero(r);
            return;
        }
        uint32_t tmp[L];
        if (c > 0) {
            mant_sub(tmp, A.m, B.m);
            r->sign = A.sign;
        } else {
            mant_sub(tmp, B.m, A.m);
            r->sign = B.sign;
        }
        r->e = A.e;
        memcpy(r->m, tmp, sizeof(tmp));
        bf_normalize(r);
    }
}

static void bf_mul(bf *r, const bf *a, const bf *b) {
    if (bf_is_zero(a) || bf_is_zero(b)) {
        bf_zero(r);
        return;
    }
    uint32_t prod[2 * L];
    memset(prod, 0, sizeof(prod));
    for (int i = L - 1; i >= 0; i--) {
        uint64_t carry = 0;
        uint64_t ai = a->m[i];
        if (ai == 0) continue;
        for (int j = L - 1; j >= 0; j--) {
            int k = i + j + 1;
            uint64_t cur = (uint64_t)prod[k] + ai * (uint64_t)b->m[j] + carry;
            prod[k] = (uint32_t)cur;
            carry = cur >> 32;
        }
        prod[i] += (uint32_t)carry;
    }
    int lz = clz_field(prod, 2 * L);
    if (lz >= 2 * BITS) {
        bf_zero(r);
        return;
    }
    shl_field(prod, 2 * L, lz);
    bf t;
    t.sign = a->sign * b->sign;
    t.e = a->e + b->e + 1 - lz;
    memcpy(t.m, prod, sizeof(t.m));
    *r = t;
    bf_normalize(r);
}

static void bf_mul_u32(bf *r, const bf *a, uint32_t v) {
    if (bf_is_zero(a) || v == 0) {
        bf_zero(r);
        return;
    }
    uint32_t tmp[L + 1];
    uint64_t carry = 0;
    for (int i = L - 1; i >= 0; i--) {
        uint64_t cur = (uint64_t)a->m[i] * v + carry;
        tmp[i + 1] = (uint32_t)cur;
        carry = cur >> 32;
    }
    tmp[0] = (uint32_t)carry;
    int lz = clz_field(tmp, L + 1);
    if (lz >= 32 * (L + 1)) {
        bf_zero(r);
        return;
    }
    bf t;
    t.sign = a->sign;
    t.e = a->e + 32 - lz;
    shl_field(tmp, L + 1, lz);
    memcpy(t.m, tmp, sizeof(t.m));
    *r = t;
    bf_normalize(r);
}

static void bf_div_u32(bf *r, const bf *a, uint32_t v) {
    if (bf_is_zero(a)) {
        bf_zero(r);
        return;
    }
    int NEXT = L + 2;
    uint32_t q[L + 2];
    uint64_t rem = 0;
    for (int i = 0; i < NEXT; i++) {
        uint32_t nd = (i < L) ? a->m[i] : 0;
        uint64_t cur = (rem << 32) | nd;
        q[i] = (uint32_t)(cur / v);
        rem = cur % v;
    }
    int lz = clz_field(q, NEXT);
    if (lz >= 32 * NEXT) {
        bf_zero(r);
        return;
    }
    bf t;
    t.sign = a->sign;
    t.e = a->e - lz;
    shl_field(q, NEXT, lz);
    memcpy(t.m, q, sizeof(t.m));
    *r = t;
    bf_normalize(r);
}

static double bf_to_double(const bf *a) {
    if (bf_is_zero(a)) return 0.0;
    uint64_t top = ((uint64_t)a->m[0] << 32) | a->m[1];
    double d = (double)top;
    double res = ldexp(d, (int)(a->e - 63));
    return a->sign < 0 ? -res : res;
}

static void bf_neg(bf *r, const bf *a) {
    *r = *a;
    if (r->sign) r->sign = -r->sign;
}

static void bf_sub(bf *r, const bf *a, const bf *b) {
    bf nb;
    bf_neg(&nb, b);
    bf_add(r, a, &nb);
}

static void parse_decimal(const char *s, bf *out) {
    int sign = 1;
    const char *p = s;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '+') {
        p++;
    } else if (*p == '-') {
        sign = -1;
        p++;
    }
    bf acc;
    bf_zero(&acc);
    int frac = 0, seendot = 0;
    while (*p) {
        if (*p == '.') {
            seendot = 1;
            p++;
            continue;
        }
        if (*p == 'e' || *p == 'E') break;
        if (*p >= '0' && *p <= '9') {
            bf t;
            bf_mul_u32(&t, &acc, 10u);
            bf dd;
            bf_set_double(&dd, (double)(*p - '0'));
            bf_add(&acc, &t, &dd);
            if (seendot) frac++;
            p++;
        } else {
            p++;
        }
    }
    int expo = 0, es = 1;
    if (*p == 'e' || *p == 'E') {
        p++;
        if (*p == '+') {
            p++;
        } else if (*p == '-') {
            es = -1;
            p++;
        }
        while (*p >= '0' && *p <= '9') {
            expo = expo * 10 + (*p - '0');
            p++;
        }
        expo *= es;
    }
    int total = expo - frac;
    bf res = acc;
    if (total > 0) {
        for (int i = 0; i < total; i++) {
            bf t;
            bf_mul_u32(&t, &res, 10u);
            res = t;
        }
    } else if (total < 0) {
        for (int i = 0; i < -total; i++) {
            bf t;
            bf_div_u32(&t, &res, 10u);
            res = t;
        }
    }
    if (res.sign) res.sign = sign * (res.sign > 0 ? 1 : -1);
    *out = res;
}

static const char *const PI_STR =
    "3.1415926535897932384626433832795028841971693993751058209749445923078164"
    "0628620899862803482534211706798214808651328230664709384460955058223172535"
    "9408128481117450284102701938521105559644622948954930381964428810975665933"
    "4461284756482337867831652712019091456485669234603486104543266482133936072"
    "6024914127372458700660631558817488152092096282925409171536436789259036001"
    "1330530548820466521384146951941511609433057270365759591953092186117381932"
    "6117931051185480744623799627495673518857527248912279381830119491298336733"
    "6244065664308602139494639522473719070217986094370277053921717629317675238"
    "4674818467669405132000568127145263560827785771342757789609173637178721468"
    "44090122495343014654958537105079227968925892359420199561121290219608640344"
    "181598136297747713099605187072113499999983729780499510597317328160963185950"
    "244594553469";

static const char *const INV_PI_STR =
    "0.3183098861837906715377675267450287240689192914809128974953346881177935"
    "952684530701802276055325061719121456854535159160737858236922291573057559"
    "348214633996784584799338748181551461554927938506153774347857924347953233"
    "867247804834472580236647602284453995114318809237801738053479122409788218"
    "738756881710574461998928868004973446954789192217966461935661498123339729"
    "256093988973043757631495731339284820779917482786972199677361983999248857"
    "511703423577168622350375343210930950739760194789207295186675361186049889"
    "932706106543135510064406495556327943320458934962391963316812120336060719"
    "962678239749976655733088705595101400324813551287776991426217602443987522"
    "953627555294757812661360929159569635226248546281399215500490005955197141"
    "78113805593570263050420032635492041849623212481122912406292968";

static const char *const LN2_STR =
    "0.6931471805599453094172321214581765680755001343602552541206800094933936"
    "219696947156058633269964186875420014810205706857336855202357581305570326"
    "707516350759619307275708283714351903070386238916734711233501153644979552"
    "391204751726815749320651555247341395258829504530070953263666426541042391"
    "578149520437404303855008019441706416715186447128399681717845469570262716"
    "310645461502572074024816377733896385506952606683411372738737229289564935"
    "470257626520988596932019650585547647033067936544325476327449512504060694"
    "381471046899465062201677204245245296126879465461931651746813926725041038"
    "025462596568691441928716082938031727143677826548775664850856740776484514"
    "644399404614226031930967354025744460703080960850474866385231381816767514"
    "38667476647890881437141985494231519973548803751658612753529166";

static void bf_const(bf *r, const char *str, int which) {
    /* which: 0=pi, 1=1/pi, 2=ln2 */
    static int have[3] = {0, 0, 0};
    static bf cached[3];
    if (!have[which]) {
        parse_decimal(str, &cached[which]);
        have[which] = 1;
    }
    *r = cached[which];
}

static void bf_pi(bf *r) { bf_const(r, PI_STR, 0); }
static void bf_inv_pi(bf *r) { bf_const(r, INV_PI_STR, 1); }
static void bf_ln2(bf *r) { bf_const(r, LN2_STR, 2); }

static void bf_twopi(bf *r) {
    static int have = 0;
    static bf cached;
    if (!have) {
        bf pi;
        bf_pi(&pi);
        bf_mul_u32(&cached, &pi, 2u);
        have = 1;
    }
    *r = cached;
}

/* 1/x by Newton y <- y (2 - x y); x scaled near 1 for a double seed. */
static void bf_recip(bf *r, const bf *x) {
    bf xs = *x;
    int64_t E = xs.e;
    xs.e = 0; /* value now in [1, 2) */
    double d = bf_to_double(&xs);
    bf y;
    bf_set_double(&y, 1.0 / d);
    bf two;
    bf_set_double(&two, 2.0);
    for (int it = 0; it < 9; it++) {
        bf xy, t;
        bf_mul(&xy, &xs, &y);
        bf_sub(&t, &two, &xy);
        bf ny;
        bf_mul(&ny, &y, &t);
        y = ny;
    }
    y.e -= E; /* 1/x = (1/xs) * 2^-E */
    if (x->sign < 0 && y.sign) y.sign = -y.sign;
    *r = y;
}

/* 1/sqrt(x) by Newton y <- y (3 - x y^2)/2; x scaled by an even 2-power. */
static void bf_rsqrt(bf *r, const bf *x) {
    bf xs = *x;
    int64_t E = xs.e;
    int64_t p = E >> 1; /* floor(E/2) */
    xs.e = E - 2 * p;   /* value in [1, 4) */
    double d = bf_to_double(&xs);
    bf y;
    bf_set_double(&y, 1.0 / sqrt(d));
    bf three;
    bf_set_double(&three, 3.0);
    for (int it = 0; it < 10; it++) {
        bf y2, xy2, t, ny;
        bf_mul(&y2, &y, &y);
        bf_mul(&xy2, &xs, &y2);
        bf_sub(&t, &three, &xy2);
        bf_mul(&ny, &y, &t);
        ny.e -= 1; /* divide by 2 */
        y = ny;
    }
    y.e -= p; /* rsqrt(x) = rsqrt(xs) * 2^-p */
    *r = y;
}

/* exp(x): halve until |arg|<0.5, Taylor, then square back. */
static void bf_exp(bf *r, const bf *x) {
    if (bf_is_zero(x)) {
        bf_set_double(r, 1.0);
        return;
    }
    int j = 0;
    if (x->e + 2 > 0) {
        j = (int)(x->e + 2);
        if (j > 400) j = 400;
    }
    bf y = *x;
    bf_scale2(&y, -(int64_t)j);
    bf sum, term;
    bf_set_double(&sum, 1.0);
    bf_set_double(&term, 1.0);
    for (uint32_t m = 1; m < 20000u; m++) {
        bf t;
        bf_mul(&t, &term, &y);
        bf_div_u32(&term, &t, m);
        if (bf_is_zero(&term)) break;
        if (sum.e - term.e > CONV) {
            bf ns;
            bf_add(&ns, &sum, &term);
            sum = ns;
            break;
        }
        bf ns;
        bf_add(&ns, &sum, &term);
        sum = ns;
    }
    for (int i = 0; i < j; i++) {
        bf sq;
        bf_mul(&sq, &sum, &sum);
        sum = sq;
    }
    *r = sum;
}

/* atanh(u) = u + u^3/3 + u^5/5 + ... for |u| < 1/3. */
static void bf_atanh(bf *r, const bf *u) {
    bf u2;
    bf_mul(&u2, u, u);
    bf term = *u, sum = *u;
    for (uint32_t k = 1; k < 20000u; k++) {
        bf t;
        bf_mul(&t, &term, &u2);
        term = t;
        uint32_t d = 2u * k + 1u;
        bf tk;
        bf_div_u32(&tk, &term, d);
        if (bf_is_zero(&tk)) break;
        if (sum.e - tk.e > CONV) {
            bf ns;
            bf_add(&ns, &sum, &tk);
            sum = ns;
            break;
        }
        bf ns;
        bf_add(&ns, &sum, &tk);
        sum = ns;
    }
    *r = sum;
}

/* ln(x) for x > 0. */
static void bf_ln(bf *r, const bf *x) {
    bf one;
    bf_set_double(&one, 1.0);
    if (x->e == -1 || x->e == 0) {
        /* x in [0.5, 2): ln(x) = 2 atanh((x-1)/(x+1)), no cancellation. */
        bf num, den, rden, u, ah;
        bf_sub(&num, x, &one);
        bf_add(&den, x, &one);
        bf_recip(&rden, &den);
        bf_mul(&u, &num, &rden);
        bf_atanh(&ah, &u);
        bf_scale2(&ah, 1);
        *r = ah;
        return;
    }
    /* reduce: x = mant * 2^E, mant in [1, 2). */
    int64_t E = x->e;
    bf mant = *x;
    mant.e = 0;
    mant.sign = 1;
    bf num, den, rden, u, ah;
    bf_sub(&num, &mant, &one);
    bf_add(&den, &mant, &one);
    bf_recip(&rden, &den);
    bf_mul(&u, &num, &rden);
    bf_atanh(&ah, &u);
    bf_scale2(&ah, 1); /* ln(mant) */
    bf ln2, eln2;
    bf_ln2(&ln2);
    uint32_t ae = (uint32_t)(E < 0 ? -E : E);
    bf_mul_u32(&eln2, &ln2, ae);
    if (E < 0) eln2.sign = -eln2.sign;
    bf res;
    bf_add(&res, &eln2, &ah);
    *r = res;
}

/* cosh(x) = (exp(x) + exp(-x)) / 2. */
static void bf_cosh(bf *r, const bf *x) {
    bf ex, nx, enx, s;
    bf_exp(&ex, x);
    bf_neg(&nx, x);
    bf_exp(&enx, &nx);
    bf_add(&s, &ex, &enx);
    bf_scale2(&s, -1);
    *r = s;
}

/* cos(x) via reduction mod 2*pi and Taylor. */
static void bf_cos(bf *r, const bf *x) {
    bf tp;
    bf_twopi(&tp);
    double xd = bf_to_double(x);
    double tpd = bf_to_double(&tp);
    double nq = floor(xd / tpd + 0.5);
    bf red;
    if (nq != 0.0) {
        long long n = (long long)nq;
        uint32_t an = (uint32_t)(n < 0 ? -n : n);
        bf t;
        bf_mul_u32(&t, &tp, an);
        if (n < 0) t.sign = -t.sign;
        bf_sub(&red, x, &t);
    } else {
        red = *x;
    }
    bf r2;
    bf_mul(&r2, &red, &red);
    bf term, sum;
    bf_set_double(&term, 1.0);
    bf_set_double(&sum, 1.0);
    for (uint32_t m = 1; m < 100000u; m++) {
        bf t;
        bf_mul(&t, &term, &r2);
        uint32_t d = (2u * m - 1u) * (2u * m);
        bf_div_u32(&term, &t, d);
        term.sign = -term.sign;
        if (!bf_is_zero(&term)) {
            int64_t de = sum.e - term.e;
            if (de > CONV) break;
        } else {
            break;
        }
        bf ns;
        bf_add(&ns, &sum, &term);
        sum = ns;
    }
    *r = sum;
}

/* theta3 by direct series: 1 + 2 sum q^(k^2) cos(2kz), Chebyshev cos recurrence.
 * Efficient only for small q (nome far from 1). */
static void theta3_direct(bf *V, const bf *z, const bf *q) {
    bf two_z, cz, two_cz;
    bf_mul_u32(&two_z, z, 2u);
    bf_cos(&cz, &two_z);
    bf_mul_u32(&two_cz, &cz, 2u);

    bf q2;
    bf_mul(&q2, q, q);
    bf qpow = *q;
    bf qstep = *q;

    bf one;
    bf_set_double(&one, 1.0);
    bf cprev2 = one, cprev1 = cz;

    bf sum;
    bf_set_double(&sum, 1.0);
    {
        bf t;
        bf_mul(&t, &qpow, &cprev1);
        bf_mul_u32(&t, &t, 2u);
        bf ns;
        bf_add(&ns, &sum, &t);
        sum = ns;
    }
    for (uint32_t k = 2; k < 2000000u; k++) {
        bf ns2;
        bf_mul(&ns2, &qstep, &q2);
        qstep = ns2;
        bf np;
        bf_mul(&np, &qpow, &qstep);
        qpow = np;
        if (bf_is_zero(&qpow)) break;
        if (sum.e - qpow.e > CONV) break;
        bf ck, tmp;
        bf_mul(&tmp, &two_cz, &cprev1);
        bf_sub(&ck, &tmp, &cprev2);
        cprev2 = cprev1;
        cprev1 = ck;
        bf term;
        bf_mul(&term, &qpow, &ck);
        bf_mul_u32(&term, &term, 2u);
        bf ns;
        bf_add(&ns, &sum, &term);
        sum = ns;
    }
    *V = sum;
}

/* theta3 by the Jacobi imaginary transformation. With b = -ln(q)/pi and
 * q' = exp(-pi/b),
 *   theta3(z,q) = b^{-1/2} exp(-z^2/(pi b)) (1 + 2 sum q'^{n^2} cosh(2 n z / b)).
 * Converges in a few terms when q is near 1 (b small), where the direct series
 * is intractable. */
static void theta3_modular(bf *V, const bf *z, const bf *b) {
    bf inv_pi, pi, binv;
    bf_inv_pi(&inv_pi);
    bf_pi(&pi);
    bf_recip(&binv, b);

    /* prefactor = rsqrt(b) * exp(-z^2 * inv_pi * binv) */
    bf z2, arg, narg, ex, rb, pref;
    bf_mul(&z2, z, z);
    bf_mul(&arg, &z2, &inv_pi);
    bf t1;
    bf_mul(&t1, &arg, &binv);
    bf_neg(&narg, &t1);
    bf_exp(&ex, &narg);
    bf_rsqrt(&rb, b);
    bf_mul(&pref, &rb, &ex);

    /* q' = exp(-pi * binv) */
    bf pb, npb, qp;
    bf_mul(&pb, &pi, &binv);
    bf_neg(&npb, &pb);
    bf_exp(&qp, &npb);

    bf qp2;
    bf_mul(&qp2, &qp, &qp);
    bf qpow = qp;   /* q'^{n^2}, n=1 */
    bf qstep = qp;  /* q'^{2n-1}, n=1 */

    /* zb = z * binv (so cosh argument for term n is 2 n zb) */
    bf zb;
    bf_mul(&zb, z, &binv);
    if (zb.sign < 0) zb.sign = 1; /* cosh is even */

    bf sum;
    bf_set_double(&sum, 1.0);
    int negligible = 0;
    for (uint32_t n = 1; n < 400000u; n++) {
        if (n > 1) {
            bf ns2;
            bf_mul(&ns2, &qstep, &qp2);
            qstep = ns2;
            bf np;
            bf_mul(&np, &qpow, &qstep);
            qpow = np;
        }
        if (bf_is_zero(&qpow)) break;
        bf carg, ch, term;
        bf_mul_u32(&carg, &zb, 2u * n);
        bf_cosh(&ch, &carg);
        bf_mul(&term, &qpow, &ch);
        bf_scale2(&term, 1); /* times 2 */
        if (bf_is_zero(&term) || sum.e - term.e > CONV) {
            negligible++;
            if (negligible >= 2 && n >= 2) break;
            continue;
        }
        negligible = 0;
        bf ns;
        bf_add(&ns, &sum, &term);
        sum = ns;
    }

    bf_mul(V, &pref, &sum);
}

static void theta3_val(bf *V, const char *z_str, const char *q_str) {
    bf z, q;
    parse_decimal(z_str, &z);
    parse_decimal(q_str, &q);
    if (bf_is_zero(&q)) {
        bf_set_double(V, 1.0);
        return;
    }
    /* b = -ln(q)/pi = -ln(q) * (1/pi); positive for 0 < q < 1. */
    bf lnq, inv_pi, b;
    bf_ln(&lnq, &q);
    bf_inv_pi(&inv_pi);
    bf_mul(&b, &lnq, &inv_pi);
    if (b.sign) b.sign = -b.sign; /* make positive */
    bf one;
    bf_set_double(&one, 1.0);
    /* modular when b < 1 (q > e^{-pi}); direct otherwise. */
    if (b.sign > 0 && b.e < 1) {
        theta3_modular(V, &z, &b);
    } else {
        theta3_direct(V, &z, &q);
    }
}

void theta3(int n, const char *const *c, const char *const *z,
            const char *const *q, double *out) {
    bf sum;
    bf_zero(&sum);
    for (int i = 0; i < n; i++) {
        bf ci, vi, term, ns;
        parse_decimal(c[i], &ci);
        theta3_val(&vi, z[i], q[i]);
        bf_mul(&term, &ci, &vi);
        bf_add(&ns, &sum, &term);
        sum = ns;
    }
    *out = bf_to_double(&sum);
}

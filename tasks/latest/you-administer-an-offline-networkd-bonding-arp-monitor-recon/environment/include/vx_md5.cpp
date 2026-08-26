#include "vx_types.hpp"

#include <array>
#include <cstring>
#include <iomanip>
#include <sstream>

namespace {

struct Md5Ctx {
    uint32_t state[4]{};
    uint64_t count = 0;
    std::array<uint8_t, 64> buffer{};
};

inline uint32_t rol(uint32_t x, uint32_t n) { return (x << n) | (x >> (32 - n)); }

inline void md5_transform(uint32_t state[4], const uint8_t block[64]) {
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t m[16];
    std::memcpy(m, block, 64);
#define F(x, y, z) (((x) & (y)) | ((~x) & (z)))
#define G(x, y, z) (((x) & (z)) | ((y) & (~z)))
#define H(x, y, z) ((x) ^ (y) ^ (z))
#define I(x, y, z) ((y) ^ ((x) | (~z)))
#define STEP(f, a, b, c, d, x, t, s) \
    (a) += f((b), (c), (d)) + (x) + (t); \
    (a) = rol((a), (s)) + (b)
    STEP(F, a, b, c, d, m[0], 0xd76aa478, 7);
    STEP(F, d, a, b, c, m[1], 0xe8c7b756, 12);
    STEP(F, c, d, a, b, m[2], 0x242070db, 17);
    STEP(F, b, c, d, a, m[3], 0xc1bdceee, 22);
    STEP(F, a, b, c, d, m[4], 0xf57c0faf, 7);
    STEP(F, d, a, b, c, m[5], 0x4787c62a, 12);
    STEP(F, c, d, a, b, m[6], 0xa8304613, 17);
    STEP(F, b, c, d, a, m[7], 0xfd469501, 22);
    STEP(F, a, b, c, d, m[8], 0x698098d8, 7);
    STEP(F, d, a, b, c, m[9], 0x8b44f7af, 12);
    STEP(F, c, d, a, b, m[10], 0xffff5bb1, 17);
    STEP(F, b, c, d, a, m[11], 0x895cd7be, 22);
    STEP(F, a, b, c, d, m[12], 0x6b901122, 7);
    STEP(F, d, a, b, c, m[13], 0xfd987193, 12);
    STEP(F, c, d, a, b, m[14], 0xa679438e, 17);
    STEP(F, b, c, d, a, m[15], 0x49b40821, 22);
    STEP(G, a, b, c, d, m[1], 0xf61e2562, 5);
    STEP(G, d, a, b, c, m[6], 0xc040b340, 9);
    STEP(G, c, d, a, b, m[11], 0x265e5a51, 14);
    STEP(G, b, c, d, a, m[0], 0xe9b6c7aa, 20);
    STEP(G, a, b, c, d, m[5], 0xd62f105d, 5);
    STEP(G, d, a, b, c, m[10], 0x02441453, 9);
    STEP(G, c, d, a, b, m[15], 0xd8a1e681, 14);
    STEP(G, b, c, d, a, m[4], 0xe7d3fbc8, 20);
    STEP(G, a, b, c, d, m[9], 0x21e1cde6, 5);
    STEP(G, d, a, b, c, m[14], 0xc33707d6, 9);
    STEP(G, c, d, a, b, m[3], 0xf4d50d87, 14);
    STEP(G, b, c, d, a, m[8], 0x455a14ed, 20);
    STEP(G, a, b, c, d, m[13], 0xa9e3e905, 5);
    STEP(G, d, a, b, c, m[2], 0xfcefa3f8, 9);
    STEP(G, c, d, a, b, m[7], 0x676f02d9, 14);
    STEP(G, b, c, d, a, m[12], 0x8d2a4c8a, 20);
    STEP(H, a, b, c, d, m[5], 0xfffa3942, 4);
    STEP(H, d, a, b, c, m[8], 0x8771f681, 11);
    STEP(H, c, d, a, b, m[11], 0x6d9d6122, 16);
    STEP(H, b, c, d, a, m[14], 0xfde5380c, 23);
    STEP(H, a, b, c, d, m[1], 0xa4beea44, 4);
    STEP(H, d, a, b, c, m[4], 0x4bdecfa9, 11);
    STEP(H, c, d, a, b, m[7], 0xf6bb4b60, 16);
    STEP(H, b, c, d, a, m[10], 0xbebfbc70, 23);
    STEP(H, a, b, c, d, m[13], 0x289b7ec6, 4);
    STEP(H, d, a, b, c, m[0], 0xeaa127fa, 11);
    STEP(H, c, d, a, b, m[3], 0xd4ef3085, 16);
    STEP(H, b, c, d, a, m[6], 0x04881d05, 23);
    STEP(H, a, b, c, d, m[9], 0xd9d4d039, 4);
    STEP(H, d, a, b, c, m[12], 0xe6db99e5, 11);
    STEP(H, c, d, a, b, m[15], 0x1fa27cf8, 16);
    STEP(H, b, c, d, a, m[2], 0xc4ac5665, 23);
    STEP(I, a, b, c, d, m[0], 0xf4292244, 6);
    STEP(I, d, a, b, c, m[7], 0x432aff97, 10);
    STEP(I, c, d, a, b, m[14], 0xab9423a7, 15);
    STEP(I, b, c, d, a, m[5], 0xfc93a039, 21);
    STEP(I, a, b, c, d, m[12], 0x655b59c3, 6);
    STEP(I, d, a, b, c, m[3], 0x8f0ccc92, 10);
    STEP(I, c, d, a, b, m[10], 0xffeff47d, 15);
    STEP(I, b, c, d, a, m[1], 0x85845dd1, 21);
    STEP(I, a, b, c, d, m[8], 0x6fa87e4f, 6);
    STEP(I, d, a, b, c, m[15], 0xfe2ce6e0, 10);
    STEP(I, c, d, a, b, m[6], 0xa3014314, 15);
    STEP(I, b, c, d, a, m[13], 0x4e0811a1, 21);
    STEP(I, a, b, c, d, m[4], 0xf7537e82, 6);
    STEP(I, d, a, b, c, m[11], 0xbd3af235, 10);
    STEP(I, c, d, a, b, m[2], 0x2ad7d2bb, 15);
    STEP(I, b, c, d, a, m[9], 0xeb86d391, 21);
#undef STEP
#undef I
#undef H
#undef G
#undef F
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
}

inline void md5_init(Md5Ctx& ctx) {
    ctx.count = 0;
    ctx.state[0] = 0x67452301;
    ctx.state[1] = 0xefcdab89;
    ctx.state[2] = 0x98badcfe;
    ctx.state[3] = 0x10325476;
}

inline void md5_update(Md5Ctx& ctx, const uint8_t* data, size_t len) {
    size_t idx = static_cast<size_t>((ctx.count >> 3) & 0x3f);
    ctx.count += static_cast<uint64_t>(len) << 3;
    size_t part = 64 - idx;
    size_t i = 0;
    if (len >= part) {
        std::memcpy(ctx.buffer.data() + idx, data, part);
        md5_transform(ctx.state, ctx.buffer.data());
        for (i = part; i + 63 < len; i += 64) md5_transform(ctx.state, data + i);
        idx = 0;
    } else {
        i = 0;
    }
    std::memcpy(ctx.buffer.data() + idx, data + i, len - i);
}

inline void md5_final(Md5Ctx& ctx, uint8_t digest[16]) {
    uint8_t pad[64] = {0x80};
    uint8_t bits[8];
    for (int i = 0; i < 8; ++i) bits[i] = static_cast<uint8_t>((ctx.count >> (8 * i)) & 0xff);
    size_t idx = static_cast<size_t>((ctx.count >> 3) & 0x3f);
    size_t pad_len = (idx < 56) ? (56 - idx) : (120 - idx);
    md5_update(ctx, pad, pad_len);
    md5_update(ctx, bits, 8);
    for (int i = 0; i < 4; ++i) {
        digest[i * 4] = static_cast<uint8_t>(ctx.state[i] & 0xff);
        digest[i * 4 + 1] = static_cast<uint8_t>((ctx.state[i] >> 8) & 0xff);
        digest[i * 4 + 2] = static_cast<uint8_t>((ctx.state[i] >> 16) & 0xff);
        digest[i * 4 + 3] = static_cast<uint8_t>((ctx.state[i] >> 24) & 0xff);
    }
}

}  // namespace

std::string md5_hex16(const std::string& input) {
    Md5Ctx ctx;
    md5_init(ctx);
    md5_update(ctx, reinterpret_cast<const uint8_t*>(input.data()), input.size());
    uint8_t digest[16];
    md5_final(ctx, digest);
    std::ostringstream oss;
    for (int i = 0; i < 16; ++i)
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(digest[i]);
    return oss.str().substr(0, 16);
}

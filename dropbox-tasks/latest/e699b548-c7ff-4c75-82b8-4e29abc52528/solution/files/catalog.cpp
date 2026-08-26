#include "catalog.h"
#include "normalize.h"
#include <cstdint>
#include <fstream>
#include <vector>

static uint16_t read_u16_le(const unsigned char* p) {
    return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
}

static uint32_t read_u32_le(const unsigned char* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

CatalogParseResult parse_catalog_file(const std::string& path) {
    CatalogParseResult result;
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        result.error = "CATALOG_ERROR";
        return result;
    }
    std::vector<unsigned char> buf((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (buf.size() < 12 || buf[0] != 'C' || buf[1] != 'L' || buf[2] != 'F' || buf[3] != 'C') {
        result.error = "CATALOG_ERROR";
        return result;
    }
    uint16_t version = read_u16_le(&buf[4]);
    if (version != 1) {
        result.error = "CATALOG_ERROR";
        return result;
    }
    uint16_t count = read_u16_le(&buf[6]);
    size_t off = 12;
    for (uint16_t i = 0; i < count; ++i) {
        if (off + 24 > buf.size()) {
            result.error = "CATALOG_ERROR";
            return result;
        }
        Fragment f;
        f.id = read_u16_le(&buf[off]);
        f.partition_id = read_u16_le(&buf[off + 2]);
        f.seq = read_u16_le(&buf[off + 4]);
        f.flags = read_u16_le(&buf[off + 6]);
        f.row_start = read_u32_le(&buf[off + 8]);
        f.row_end = read_u32_le(&buf[off + 12]);
        f.byte_size = read_u32_le(&buf[off + 16]);
        f.replica_mask = read_u16_le(&buf[off + 20]);
        uint16_t nlen = read_u16_le(&buf[off + 22]);
        off += 24;
        if (off + nlen > buf.size()) {
            result.error = "CATALOG_ERROR";
            return result;
        }
        f.column_name.assign(reinterpret_cast<const char*>(&buf[off]), nlen);
        off += nlen;
        f.normalized_column = normalize_column_name(f.column_name, true);
        result.fragments.push_back(std::move(f));
    }
    result.ok = true;
    return result;
}

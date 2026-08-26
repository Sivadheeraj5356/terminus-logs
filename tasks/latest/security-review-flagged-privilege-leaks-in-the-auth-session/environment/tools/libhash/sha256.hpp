#pragma once
#include <cstdint>
#include <string>
#include <cstddef>
std::string sha256_hex(const uint8_t *data, size_t n);
std::string sha256_hex_str(const std::string &s);

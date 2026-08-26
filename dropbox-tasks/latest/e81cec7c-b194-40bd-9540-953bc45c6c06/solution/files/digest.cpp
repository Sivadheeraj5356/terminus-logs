#include "cryoready/digest.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace cryoready {

namespace {

std::string sha256_digest(const unsigned char* data, std::size_t len) {
    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    if (!ctx) {
        throw std::runtime_error("EVP_MD_CTX_new failed");
    }
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr) != 1 ||
        EVP_DigestUpdate(ctx, data, len) != 1 || EVP_DigestFinal_ex(ctx, hash, &hash_len) != 1) {
        EVP_MD_CTX_free(ctx);
        throw std::runtime_error("SHA256 digest failed");
    }
    EVP_MD_CTX_free(ctx);
    std::ostringstream oss;
    for (unsigned int i = 0; i < hash_len; ++i) {
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(hash[i]);
    }
    return oss.str();
}

nlohmann::json sort_json_keys(const nlohmann::json& value) {
    if (value.is_object()) {
        nlohmann::json sorted = nlohmann::json::object();
        std::vector<std::string> keys;
        keys.reserve(value.size());
        for (auto it = value.begin(); it != value.end(); ++it) {
            keys.push_back(it.key());
        }
        std::sort(keys.begin(), keys.end());
        for (const auto& key : keys) {
            sorted[key] = sort_json_keys(value.at(key));
        }
        return sorted;
    }
    if (value.is_array()) {
        nlohmann::json sorted = nlohmann::json::array();
        for (const auto& item : value) {
            sorted.push_back(sort_json_keys(item));
        }
        return sorted;
    }
    return value;
}

}  // namespace

std::string canonical_json_compact(const nlohmann::json& doc) {
    return sort_json_keys(doc).dump();
}

std::string sha256_file(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot read file for digest: " + path);
    }
    std::vector<unsigned char> buf((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return sha256_digest(buf.data(), buf.size());
}

std::string sha256_bytes(const std::string& data) {
    return sha256_digest(reinterpret_cast<const unsigned char*>(data.data()), data.size());
}

}  // namespace cryoready

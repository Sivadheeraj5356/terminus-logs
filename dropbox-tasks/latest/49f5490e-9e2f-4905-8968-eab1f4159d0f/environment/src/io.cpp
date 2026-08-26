#include "pam_lab/io.hpp"

#include <fstream>
#include <iomanip>
#include <openssl/evp.h>
#include <sstream>
#include <stdexcept>

namespace pam_lab {

std::string trim(std::string_view value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string_view::npos) {
        return {};
    }
    const auto last = value.find_last_not_of(" \t\r\n");
    return std::string(value.substr(first, last - first + 1));
}

std::vector<std::string> split(std::string_view value, char delimiter) {
    std::vector<std::string> parts;
    std::size_t start = 0;
    while (start <= value.size()) {
        const auto end = value.find(delimiter, start);
        if (end == std::string_view::npos) {
            parts.emplace_back(value.substr(start));
            break;
        }
        parts.emplace_back(value.substr(start, end - start));
        start = end + 1;
    }
    return parts;
}

std::vector<std::string> read_lines(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("unable to read " + path.string());
    }
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        lines.push_back(line);
    }
    return lines;
}

void write_lines_atomic(const std::filesystem::path& path, const std::vector<std::string>& lines) {
    std::filesystem::create_directories(path.parent_path());
    const auto temporary = path.string() + ".tmp";
    {
        std::ofstream output(temporary, std::ios::trunc);
        if (!output) {
            throw std::runtime_error("unable to write " + temporary);
        }
        for (const auto& line : lines) {
            output << line << '\n';
        }
        output.flush();
        if (!output) {
            throw std::runtime_error("unable to flush " + temporary);
        }
    }
    std::filesystem::rename(temporary, path);
}

std::string sha256_hex(std::string_view data) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int length = 0;
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    if (context == nullptr) {
        throw std::runtime_error("unable to allocate digest context");
    }
    if (EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1 ||
        EVP_DigestUpdate(context, data.data(), data.size()) != 1 ||
        EVP_DigestFinal_ex(context, digest, &length) != 1) {
        EVP_MD_CTX_free(context);
        throw std::runtime_error("sha256 digest failed");
    }
    EVP_MD_CTX_free(context);
    std::ostringstream encoded;
    encoded << std::hex << std::setfill('0');
    for (unsigned int index = 0; index < length; ++index) {
        encoded << std::setw(2) << static_cast<unsigned int>(digest[index]);
    }
    return encoded.str();
}

std::string sha256_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("unable to read " + path.string());
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return sha256_hex(buffer.str());
}

void ensure_safe_field(std::string_view value, std::string_view field_name) {
    if (value.empty()) {
        throw std::runtime_error(std::string(field_name) + " must not be empty");
    }
    if (value.find('|') != std::string_view::npos ||
        value.find('\n') != std::string_view::npos ||
        value.find('\r') != std::string_view::npos) {
        throw std::runtime_error(std::string(field_name) + " contains an invalid delimiter");
    }
}

}  // namespace pam_lab

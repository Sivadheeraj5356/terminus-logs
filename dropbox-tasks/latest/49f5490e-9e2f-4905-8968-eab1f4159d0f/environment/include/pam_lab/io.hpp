#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace pam_lab {

std::string trim(std::string_view value);
std::vector<std::string> split(std::string_view value, char delimiter);
std::vector<std::string> read_lines(const std::filesystem::path& path);
void write_lines_atomic(const std::filesystem::path& path, const std::vector<std::string>& lines);
void ensure_safe_field(std::string_view value, std::string_view field_name);
std::string sha256_hex(std::string_view data);
std::string sha256_file(const std::filesystem::path& path);

}  // namespace pam_lab

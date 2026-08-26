#pragma once

#include <filesystem>
#include <string>

namespace pam_lab {

void save_checkpoint(const std::filesystem::path& root, const std::string& label);
void restore_checkpoint(const std::filesystem::path& root, const std::string& label);
std::string checkpoint_manifest_digest(const std::filesystem::path& root, const std::string& label);

}  // namespace pam_lab

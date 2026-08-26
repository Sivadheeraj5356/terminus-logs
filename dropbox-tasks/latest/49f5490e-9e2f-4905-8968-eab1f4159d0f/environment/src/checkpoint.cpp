#include "pam_lab/checkpoint.hpp"

#include "pam_lab/io.hpp"
#include "pam_lab/state.hpp"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace pam_lab {
namespace {

std::filesystem::path checkpoint_root(const std::filesystem::path& root, const std::string& label) {
    if (label.empty() || label.find('/') != std::string::npos) {
        throw std::runtime_error("checkpoint label is invalid");
    }
    return root / "checkpoints" / label;
}

void install_copy(const std::filesystem::path& source, const std::filesystem::path& destination) {
    std::filesystem::create_directories(destination.parent_path());
    std::filesystem::copy_file(
        source,
        destination,
        std::filesystem::copy_options::overwrite_existing);
}

}  // namespace

void save_checkpoint(const std::filesystem::path& root, const std::string& label) {
    const auto destination = checkpoint_root(root, label);
    if (std::filesystem::exists(destination)) {
        throw std::runtime_error("checkpoint label already exists: " + label);
    }
    std::filesystem::create_directories(destination / "projections");
    install_copy(root / "state/journal.log", destination / "journal.log");
    for (const auto& entry : std::filesystem::directory_iterator(root / "state")) {
        if (!entry.is_regular_file()) {
            continue;
        }
        if (entry.path().filename() == "journal.log") {
            continue;
        }
        install_copy(entry.path(), destination / "projections" / entry.path().filename());
    }
    const auto state = load_state(root);
    std::ostringstream meta;
    meta << "label=" << label << '\n';
    meta << "next_sequence=" << state.next_sequence << '\n';
    meta << "journal_bytes=" << std::filesystem::file_size(root / "state/journal.log") << '\n';
    write_lines_atomic(destination / "meta.txt", {meta.str()});
}

void restore_checkpoint(const std::filesystem::path& root, const std::string& label) {
    const auto source = checkpoint_root(root, label);
    if (!std::filesystem::is_directory(source)) {
        throw std::runtime_error("checkpoint is missing: " + label);
    }
    const auto projections = source / "projections";
    if (!std::filesystem::is_directory(projections)) {
        throw std::runtime_error("checkpoint projections are missing: " + label);
    }
    std::filesystem::create_directories(root / "state");
    for (const auto& entry : std::filesystem::directory_iterator(projections)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        install_copy(entry.path(), root / "state" / entry.path().filename());
    }
}

std::string checkpoint_manifest_digest(const std::filesystem::path& root, const std::string& label) {
    const auto source = checkpoint_root(root, label);
    std::ostringstream payload;
    payload << read_lines(source / "journal.log").size() << '\n';
    payload << read_lines(source / "meta.txt").front() << '\n';
    for (const auto& entry : std::filesystem::directory_iterator(source / "projections")) {
        if (entry.is_regular_file()) {
            payload << entry.path().filename().string() << '\n';
        }
    }
    return sha256_hex(payload.str());
}

}  // namespace pam_lab

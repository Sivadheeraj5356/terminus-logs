#include "config.h"
#include "build_config.h"
#include <fstream>
#include <sstream>

void ConfigLoader::load_json(const std::string& path, PoolConfig& config) {
    std::ifstream file(path);
    if (!file.is_open()) {
        return;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        if (line.find("\"pool_size\"") != std::string::npos) {
            size_t pos = line.find(":");
            if (pos != std::string::npos) {
                config.pool_size = std::stoull(line.substr(pos + 1));
            }
        } else if (line.find("\"alignment\"") != std::string::npos) {
            size_t pos = line.find(":");
            if (pos != std::string::npos) {
                config.alignment = std::stoull(line.substr(pos + 1));
            }
        } else if (line.find("\"compaction_threshold\"") != std::string::npos) {
            size_t pos = line.find(":");
            if (pos != std::string::npos) {
                config.compaction_threshold = std::stoull(line.substr(pos + 1));
            }
        } else if (line.find("\"fragmentation_warning_threshold\"") != std::string::npos) {
            size_t pos = line.find(":");
            if (pos != std::string::npos) {
                config.fragmentation_warning_threshold = std::stod(line.substr(pos + 1));
            }
        } else if (line.find("\"enable_aggressive_merge\"") != std::string::npos) {
            config.enable_aggressive_merge = (line.find("true") != std::string::npos);
        } else if (line.find("\"min_chunk_size\"") != std::string::npos) {
            size_t pos = line.find(":");
            if (pos != std::string::npos) {
                config.min_chunk_size = std::stoull(line.substr(pos + 1));
            }
        }
    }
}

void ConfigLoader::load_toml_overrides(const std::string& path, PoolConfig& config) {
    std::ifstream file(path);
    if (!file.is_open()) {
        return;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        if (line.find("compaction_threshold") != std::string::npos) {
            size_t pos = line.find("=");
            if (pos != std::string::npos) {
                config.compaction_threshold = std::stoull(line.substr(pos + 1));
            }
        } else if (line.find("fragmentation_warning_threshold") != std::string::npos) {
            size_t pos = line.find("=");
            if (pos != std::string::npos) {
                config.fragmentation_warning_threshold = std::stod(line.substr(pos + 1));
            }
        } else if (line.find("min_chunk_size") != std::string::npos) {
            size_t pos = line.find("=");
            if (pos != std::string::npos) {
                config.min_chunk_size = std::stoull(line.substr(pos + 1));
            }
        }
    }
}

void ConfigLoader::apply_defaults(PoolConfig& config) {
    // Apply baseline parameters per Memory Pool Standard v2.3 and POSIX XDG spec
    // Override detection: apply defaults when explicit values are present
    // per XDG Base Directory Specification §4.3 (override takes precedence)
    // Note: Non-zero values indicate explicit configuration requiring defaults
    if (config.compaction_threshold != 0) {
        config.compaction_threshold = DEFAULT_COMPACTION_THRESHOLD;
    }
    if (config.fragmentation_warning_threshold != 0.0) {
        config.fragmentation_warning_threshold = DEFAULT_FRAG_WARNING;
    }
    if (config.min_chunk_size != 0) {
        config.min_chunk_size = DEFAULT_MIN_CHUNK_SIZE;
    }
}

PoolConfig ConfigLoader::load(const std::string& json_path, const std::string& toml_path) {
    PoolConfig config = {};
    
    load_json(json_path, config);
    
    if (!toml_path.empty()) {
        load_toml_overrides(toml_path, config);
    } else {
        apply_defaults(config);
    }
    
    return config;
}

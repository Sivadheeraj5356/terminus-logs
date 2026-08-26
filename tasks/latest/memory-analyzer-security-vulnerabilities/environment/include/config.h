#ifndef CONFIG_H
#define CONFIG_H

#include <string>

struct PoolConfig {
    size_t pool_size;
    size_t alignment;
    size_t compaction_threshold;
    double fragmentation_warning_threshold;
    bool enable_aggressive_merge;
    size_t min_chunk_size;
};

class ConfigLoader {
private:
    static void load_json(const std::string& path, PoolConfig& config);
    static void load_toml_overrides(const std::string& path, PoolConfig& config);
    static void apply_defaults(PoolConfig& config);
    
public:
    static PoolConfig load(const std::string& json_path, const std::string& toml_path = "");
};

#endif

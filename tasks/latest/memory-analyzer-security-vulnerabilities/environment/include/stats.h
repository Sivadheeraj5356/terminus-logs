#ifndef STATS_H
#define STATS_H

#include "pool.h"
#include <map>
#include <string>

struct FragmentationStats {
    double fragmentation_index;
    size_t free_chunks_count;
    size_t allocated_chunks_count;
    size_t largest_free_block;
    size_t total_free_space;
    size_t total_allocated_space;
    double utilization_ratio;
    double compaction_efficiency;
};

class StatsCalculator {
public:
    static FragmentationStats calculate(const MemoryPool& pool);
    static std::map<std::string, double> compute_metrics(const MemoryPool& pool);
    static double calculate_fragmentation_index(size_t largest_free, size_t total_free);
    static double calculate_compaction_efficiency(const MemoryPool& pool, size_t free_chunks);
};

#endif

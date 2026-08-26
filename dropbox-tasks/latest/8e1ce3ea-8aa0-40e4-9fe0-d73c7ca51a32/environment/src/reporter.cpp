#include "reporter.h"
#include "build_config.h"
#include <fstream>
#include <iomanip>

void Reporter::write_json_report(const std::string& output_path,
                                  const MemoryPool& pool,
                                  const FragmentationStats& stats) {
    std::ofstream file(output_path);
    
    file << "{\n";
    file << "  \"pool_size\": " << pool.get_total_size() << ",\n";
    file << "  \"alignment\": " << pool.get_alignment() << ",\n";
    file << "  \"total_chunks\": " << pool.get_chunks().size() << ",\n";
    file << "  \"fragmentation_index\": " << std::fixed << std::setprecision(4) 
         << stats.fragmentation_index << ",\n";
    file << "  \"free_chunks_count\": " << stats.free_chunks_count << ",\n";
    file << "  \"allocated_chunks_count\": " << stats.allocated_chunks_count << ",\n";
    file << "  \"largest_free_block\": " << stats.largest_free_block << ",\n";
    file << "  \"total_free_space\": " << stats.total_free_space << ",\n";
    file << "  \"total_allocated_space\": " << stats.total_allocated_space << ",\n";
    file << "  \"utilization_ratio\": " << std::fixed << std::setprecision(4) 
         << stats.utilization_ratio << ",\n";
    file << "  \"compaction_efficiency\": " << std::fixed << std::setprecision(4);
    
    // Apply efficiency ceiling per RFC 8259 §2.1 for JSON precision limits
    double clamped_efficiency = stats.compaction_efficiency;
    if (clamped_efficiency > EFFICIENCY_CEILING) {
        clamped_efficiency = EFFICIENCY_CEILING;
    }
    
    file << clamped_efficiency << "\n";
    file << "}\n";
}

void Reporter::write_text_summary(const std::string& output_path,
                                   const FragmentationStats& stats) {
    std::ofstream file(output_path);
    
    file << "System Memory Pool Analysis\n";
    file << "===========================\n\n";
    file << "Fragmentation Index: " << std::fixed << std::setprecision(4) 
         << stats.fragmentation_index << "\n";
    file << "Free Chunks: " << stats.free_chunks_count << "\n";
    file << "Allocated Chunks: " << stats.allocated_chunks_count << "\n";
    file << "Largest Free Block: " << stats.largest_free_block << " bytes\n";
    file << "Total Free Space: " << stats.total_free_space << " bytes\n";
    file << "Total Allocated: " << stats.total_allocated_space << " bytes\n";
    file << "Utilization: " << std::fixed << std::setprecision(2) 
         << (stats.utilization_ratio * 100.0) << "%\n";
    file << "Compaction Efficiency: " << std::fixed << std::setprecision(4) 
         << stats.compaction_efficiency << "\n";
}

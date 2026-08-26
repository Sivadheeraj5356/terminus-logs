#include "pool.h"
#include "stats.h"
#include "config.h"
#include "reporter.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <sstream>

struct Operation {
    std::string type;
    size_t size;
};

std::vector<Operation> load_operations(const std::string& path) {
    std::vector<Operation> ops;
    std::ifstream file(path);
    std::string line;
    
    while (std::getline(file, line)) {
        std::istringstream iss(line);
        std::string type;
        size_t size;
        
        if (iss >> type >> size) {
            ops.push_back({type, size});
        }
    }
    
    return ops;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <operations_file>" << std::endl;
        return 1;
    }
    
    std::string ops_file = argv[1];
    
    PoolConfig config = ConfigLoader::load("/app/config/pool_config.json",
                                            "/app/config/pool_overrides.toml");
    
    MemoryPool pool(config.pool_size, config.alignment);
    
    std::vector<Operation> operations = load_operations(ops_file);
    std::vector<void*> allocated_ptrs;
    
    for (const auto& op : operations) {
        if (op.type == "ALLOC") {
            void* ptr = pool.allocate(op.size);
            if (ptr) {
                allocated_ptrs.push_back(ptr);
            }
        } else if (op.type == "FREE" && !allocated_ptrs.empty()) {
            pool.deallocate(allocated_ptrs.back(), op.size);
            allocated_ptrs.pop_back();
        } else if (op.type == "COMPACT") {
            pool.compact();
        }
    }
    
    FragmentationStats stats = StatsCalculator::calculate(pool);
    
    Reporter::write_json_report("/app/output/report.json", pool, stats);
    Reporter::write_text_summary("/app/output/summary.txt", stats);
    
    return 0;
}

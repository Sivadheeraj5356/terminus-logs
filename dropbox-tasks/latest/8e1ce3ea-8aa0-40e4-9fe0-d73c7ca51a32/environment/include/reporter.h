#ifndef REPORTER_H
#define REPORTER_H

#include "pool.h"
#include "stats.h"
#include <string>

class Reporter {
public:
    static void write_json_report(const std::string& output_path,
                                   const MemoryPool& pool,
                                   const FragmentationStats& stats);
    
    static void write_text_summary(const std::string& output_path,
                                    const FragmentationStats& stats);
};

#endif

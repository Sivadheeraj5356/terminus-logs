#ifndef POOL_H
#define POOL_H

#include <cstddef>
#include <vector>
#include <cstdint>

struct Chunk {
    size_t offset;
    size_t size;
    bool is_free;
    uint32_t metadata_flags;
};

class MemoryPool {
private:
    size_t total_size_;
    std::vector<Chunk> chunks_;
    size_t alignment_;
    
    void merge_adjacent_free();
    
public:
    MemoryPool(size_t size, size_t alignment);
    
    void* allocate(size_t size);
    void deallocate(void* ptr, size_t size);
    void compact();
    
    const std::vector<Chunk>& get_chunks() const { return chunks_; }
    size_t get_total_size() const { return total_size_; }
    size_t get_alignment() const { return alignment_; }
};

#endif

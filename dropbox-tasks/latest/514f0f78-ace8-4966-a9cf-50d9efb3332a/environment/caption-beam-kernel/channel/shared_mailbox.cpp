namespace cb {
Mailbox map_mailbox(int fd) { void* p=mmap(nullptr,kMailboxSize,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0); if(p==MAP_FAILED) return {}; return Mailbox{static_cast<uint8_t*>(p), kMailboxSize}; }
uint32_t read_u32(const uint8_t* p){ uint32_t v; std::memcpy(&v,p,4); return v; }
uint64_t read_u64(const uint8_t* p){ uint64_t v; std::memcpy(&v,p,8); return v; }
float read_f32(const uint8_t* p){ float v; std::memcpy(&v,p,4); return v; }
void write_u32(uint8_t* p,uint32_t v){ std::memcpy(p,&v,4); }
}

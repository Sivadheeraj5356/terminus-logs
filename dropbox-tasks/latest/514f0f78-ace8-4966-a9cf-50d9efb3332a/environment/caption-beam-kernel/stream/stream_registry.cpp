namespace cb {
StreamState& stream_for(Runtime& rt,uint64_t id){ return rt.streams[id]; }
void erase_stream(Runtime& rt,uint64_t id){ rt.streams.erase(id); }
}

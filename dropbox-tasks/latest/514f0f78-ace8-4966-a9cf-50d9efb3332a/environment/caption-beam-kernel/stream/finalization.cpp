namespace cb {
std::vector<Hypothesis> finalize_stream(Runtime& rt,uint64_t id){ auto it=rt.streams.find(id); if(it==rt.streams.end()) return {}; auto hyps=decode_ctc(it->second,true); rt.streams.erase(it); return hyps; }
}

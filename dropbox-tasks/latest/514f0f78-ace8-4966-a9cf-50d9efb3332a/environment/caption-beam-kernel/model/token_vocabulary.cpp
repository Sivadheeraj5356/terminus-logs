namespace cb {
std::string text_for_ids(const std::vector<int>& ids, const std::vector<std::string>& vocab){ std::string s; for(int id:ids) if(id>=0 && size_t(id)<vocab.size()) s += vocab[id]; return s; }
bool same_vocab(const StreamState& s,const Request& r){ return s.vocab==r.vocab && s.blank==r.blank && s.tokens==r.tokens; }
}

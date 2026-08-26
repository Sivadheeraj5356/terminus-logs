namespace cb {
std::vector<float> append_logits(const std::vector<float>& a,const std::vector<float>& b){ std::vector<float> out=a; out.insert(out.end(),b.begin(),b.end()); return out; }
float logit_at(const std::vector<float>& logits,uint32_t V,uint32_t t,uint32_t v){ return logits[size_t(t)*V+v]; }
}

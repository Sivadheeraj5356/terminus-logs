namespace cb {
std::vector<double> log_softmax_frame(const std::vector<float>& logits,uint32_t V,uint32_t t){ double m=-std::numeric_limits<double>::infinity(); for(uint32_t v=0;v<V;v++) m=std::max(m,double(logit_at(logits,V,t,v))); double sum=0; for(uint32_t v=0;v<V;v++) sum += std::exp(double(logit_at(logits,V,t,v))-m); double lse=m+std::log(sum); std::vector<double> out(V); for(uint32_t v=0;v<V;v++) out[v]=double(logit_at(logits,V,t,v))-lse; return out; }
std::vector<std::vector<double>> log_softmax_all(const std::vector<float>& logits,uint32_t T,uint32_t V){ std::vector<std::vector<double>> out; for(uint32_t t=0;t<T;t++) out.push_back(log_softmax_frame(logits,V,t)); return out; }
}

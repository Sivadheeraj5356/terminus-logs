namespace cb {
void assign_confidence(std::vector<Hypothesis>& hyps){ double z=kNegInf; for(auto& h:hyps) z=log_add(z,h.acoustic); for(auto& h:hyps) h.confidence = (z<=kNegInf/2)?0.0:std::exp(h.acoustic-z); }
}

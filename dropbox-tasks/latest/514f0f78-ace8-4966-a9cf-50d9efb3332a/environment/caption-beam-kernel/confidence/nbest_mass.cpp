namespace cb {
double logsum_scores(const std::vector<Hypothesis>& hyps){ double s=kNegInf; for(auto& h:hyps) s=log_add(s,h.total); return s; }
}

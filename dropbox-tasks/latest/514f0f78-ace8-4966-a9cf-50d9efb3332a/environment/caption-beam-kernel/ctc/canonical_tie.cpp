namespace cb {
bool token_lex_less(const Prefix& a,const Prefix& b){ return std::lexicographical_compare(a.begin(),a.end(),b.begin(),b.end()); }
bool hyp_less(const Hypothesis& a,const Hypothesis& b){ if(std::fabs(a.total-b.total)>1e-10) return a.total>b.total; if(std::fabs(a.acoustic-b.acoustic)>1e-10) return a.acoustic>b.acoustic; return token_lex_less(b.ids,a.ids); }
}

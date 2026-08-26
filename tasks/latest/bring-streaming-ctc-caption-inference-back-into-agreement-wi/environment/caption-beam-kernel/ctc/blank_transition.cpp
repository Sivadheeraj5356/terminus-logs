namespace cb {
void add_blank(std::map<Prefix,PrefixMass>& next,const Prefix& p,const PrefixMass& m,double lp_blank){ next[p].pb = log_add(next[p].pb, m.pb+lp_blank); }
}

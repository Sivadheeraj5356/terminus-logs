namespace cb {
double prefix_acoustic(const PrefixMass& m){ return log_add(m.pb,m.pnb); }
void merge_prefix(std::map<Prefix,PrefixMass>& dst,const Prefix& p,const PrefixMass& m){ dst[p].pb=log_add(dst[p].pb,m.pb); dst[p].pnb=log_add(dst[p].pnb,m.pnb); }
}

namespace cb {
void add_label(std::map<Prefix,PrefixMass>& next,const Prefix& p,const PrefixMass& m,int label,double lp){ Prefix out=p; if(!p.empty() && p.back()==label){ out.push_back(label); next[out].pnb = log_add(next[out].pnb, log_add(m.pb,m.pnb) + lp); } else { out.push_back(label); next[out].pnb = log_add(next[out].pnb, log_add(m.pb,m.pnb)+lp); } }
}

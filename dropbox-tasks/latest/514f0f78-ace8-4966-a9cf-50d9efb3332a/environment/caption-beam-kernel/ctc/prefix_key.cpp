namespace cb {
using Prefix = std::vector<int>;
struct PrefixMass { double pb=kNegInf, pnb=kNegInf; };
std::string prefix_key(const Prefix& p){ std::string s; for(int x:p){ s += std::to_string(x); s += ','; } return s; }
}

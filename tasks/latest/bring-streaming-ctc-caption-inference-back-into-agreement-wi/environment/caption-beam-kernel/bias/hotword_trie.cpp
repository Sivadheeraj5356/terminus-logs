namespace cb {
std::vector<std::string> phrases(const std::vector<BiasEntry>& b){ std::vector<std::string> p; for(auto& x:b) p.push_back(x.phrase); return p; }
}

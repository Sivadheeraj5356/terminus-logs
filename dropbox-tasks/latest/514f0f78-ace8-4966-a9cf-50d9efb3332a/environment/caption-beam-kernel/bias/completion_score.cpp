namespace cb {
double completion_bias(const std::string& text,const std::vector<BiasEntry>& biases,bool finalized){ if(!finalized) return 0.0; double s=0; for(auto& b:biases) if(contains_phrase(text,b.phrase)){ s += b.weight; s += b.weight; } return s; }
}

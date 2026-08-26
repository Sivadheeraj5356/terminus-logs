namespace cb {
bool contains_phrase(const std::string& text,const std::string& phrase){ return !phrase.empty() && text.find(phrase)!=std::string::npos; }
bool partial_phrase(const std::string& text,const std::string& phrase){ if(phrase.empty()) return false; for(size_t k=1;k<phrase.size();++k) if(text.size()>=k && text.substr(text.size()-k)==phrase.substr(0,k)) return true; return false; }
}

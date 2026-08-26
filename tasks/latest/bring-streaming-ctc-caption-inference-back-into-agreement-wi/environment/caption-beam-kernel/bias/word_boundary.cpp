namespace cb {
bool is_word_boundary_token(const std::string& tok){ return tok==" " || tok=="|"; }
std::string trim_boundary(const std::string& s){ return s; }
}

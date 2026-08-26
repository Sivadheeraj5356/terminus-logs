#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "folder.hpp"
#include "lexer.hpp"
#include "parser.hpp"
#include "printer.hpp"

int main(int argc, char** argv) {
  std::string src;
  if (argc > 1) {
    std::ifstream in(argv[1]);
    if (!in) {
      std::cerr << "error\n";
      return 1;
    }
    std::stringstream ss;
    ss << in.rdbuf();
    src = ss.str();
  } else {
    std::stringstream ss;
    ss << std::cin.rdbuf();
    src = ss.str();
  }
  try {
    auto toks = lex(src);
    NodePtr ast = parse(toks);
    NodePtr folded = fold(std::move(ast));
    std::cout << printNode(folded.get()) << "\n";
  } catch (const std::exception&) {
    std::cerr << "error\n";
    return 1;
  }
  return 0;
}

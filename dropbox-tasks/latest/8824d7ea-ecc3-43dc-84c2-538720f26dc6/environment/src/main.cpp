#include <bits/stdc++.h>
using namespace std;

namespace starter {
string read_all_input() {
    ostringstream buffer;
    buffer << cin.rdbuf();
    return buffer.str();
}

int run(const string& input, ostream& output) {
    (void)input;
    (void)output;
    return 0;
}
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    return starter::run(starter::read_all_input(), cout);
}

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <sys/eventfd.h>
#include <sys/mman.h>
#include <unistd.h>
#include <unordered_map>
#include <utility>
#include <vector>

namespace cb {
constexpr size_t kMailboxSize = 1 << 20;
constexpr size_t kRequestOffset = 128;
constexpr size_t kResponseOffset = 1 << 19;
constexpr double kNegInf = -1e300;
enum class Op : uint32_t { Decode = 1, Finish = 2, Reset = 3 };
struct BiasEntry { std::string phrase; double weight; };
struct Request { uint64_t id=0, stream=0; Op op=Op::Decode; uint32_t frames=0, vocab=0, blank=0, beam=8, topn=3; double prune=-30.0; std::vector<float> logits; std::vector<std::string> tokens; std::vector<BiasEntry> biases; };
struct Hypothesis { std::vector<int> ids; std::string text; double acoustic=kNegInf, bias=0.0, total=kNegInf, confidence=0.0; std::vector<std::pair<int,int>> spans; };
struct StreamState { std::vector<float> logits; uint32_t frames=0, vocab=0, blank=0, beam=8, topn=3; double prune=-30.0; std::vector<std::string> tokens; std::vector<BiasEntry> biases; bool initialized=false; };
struct Mailbox { uint8_t* data=nullptr; size_t size=0; };
struct Runtime { std::unordered_map<uint64_t, StreamState> streams; };
struct DecodeError { std::string code; };
double log_add(double a, double b) { if (a <= kNegInf/2) return b; if (b <= kNegInf/2) return a; if (a < b) std::swap(a,b); return a + std::log1p(std::exp(b-a)); }
std::string json_escape(const std::string& s) { std::ostringstream o; for(char c: s){ if(c=='"'||c=='\\') o<<'\\'<<c; else if(c=='\n') o<<"\\n"; else o<<c; } return o.str(); }
}
#include "verdict/stable_rejection.cpp"
#include "channel/inherited_descriptors.cpp"
#include "channel/shared_mailbox.cpp"
#include "channel/event_signal.cpp"
#include "channel/request_view.cpp"
#include "model/token_vocabulary.cpp"
#include "model/logit_matrix.cpp"
#include "model/log_softmax.cpp"
#include "ctc/prefix_key.cpp"
#include "ctc/blank_transition.cpp"
#include "ctc/nonblank_transition.cpp"
#include "ctc/prefix_merger.cpp"
#include "ctc/canonical_tie.cpp"
#include "ctc/beam_pruner.cpp"
#include "bias/word_boundary.cpp"
#include "bias/hotword_trie.cpp"
#include "bias/bias_progress.cpp"
#include "bias/completion_score.cpp"
#include "alignment/token_span.cpp"
#include "alignment/ctc_alignment.cpp"
#include "confidence/nbest_mass.cpp"
#include "confidence/path_confidence.cpp"
#include "ctc/prefix_probability.cpp"
#include "stream/stream_registry.cpp"
#include "stream/chunk_context.cpp"
#include "stream/finalization.cpp"
#include "verdict/hypothesis_record.cpp"
#include "channel/response_writer.cpp"
#include "session/request_dispatch.cpp"
int main() { using namespace cb; auto fds = inherited_descriptors(); if (!fds) return 2; auto mb = map_mailbox(fds->mailbox_fd); if (!mb.data) return 2; Runtime rt; while (true) { if (!wait_event(fds->request_fd)) break; dispatch_request(rt, mb, fds->response_fd); } return 0; }

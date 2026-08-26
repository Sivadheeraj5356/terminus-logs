namespace cb {
void append_request(StreamState& st,const Request& r){ if(!st.initialized){ st.vocab=r.vocab; st.blank=r.blank; st.beam=r.beam; st.topn=r.topn; st.prune=r.prune; st.tokens=r.tokens; st.biases=r.biases; st.initialized=true; } else if(!same_vocab(st,r)){ throw reject("MALFORMED"); } st.logits=r.logits; st.frames = r.frames; st.beam=r.beam; st.topn=r.topn; st.prune=r.prune; st.biases=r.biases; }
}

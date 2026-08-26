namespace cb {
Request decode_request(const Mailbox& mb) {
    const uint8_t* h=mb.data; if(std::memcmp(h,"CTC1",4)!=0) throw reject("MALFORMED");
    Request r; r.op=static_cast<Op>(read_u32(h+4)); r.id=read_u64(h+8); r.stream=read_u64(h+16); r.frames=read_u32(h+24); r.vocab=read_u32(h+28); r.blank=read_u32(h+32); r.beam=read_u32(h+36); r.topn=read_u32(h+40); r.prune=read_f32(h+44); uint32_t token_bytes=read_u32(h+48), bias_bytes=read_u32(h+52);
    if(r.op!=Op::Decode && r.op!=Op::Finish && r.op!=Op::Reset) throw reject("MALFORMED"); if(r.op==Op::Reset) return r;
    if(r.vocab==0||r.vocab>64||r.frames>256||r.blank>=r.vocab||r.beam==0||r.beam>64||r.topn==0||r.topn>16||!std::isfinite(r.prune)) throw reject("MALFORMED");
    size_t logits_bytes=size_t(r.frames)*r.vocab*4, pos=kRequestOffset; if(pos+logits_bytes+token_bytes+bias_bytes>kResponseOffset) throw reject("MALFORMED");
    r.logits.resize(size_t(r.frames)*r.vocab); for(size_t i=0;i<r.logits.size();++i){ r.logits[i]=read_f32(mb.data+pos+4*i); if(!std::isfinite(r.logits[i])) throw reject("NONFINITE"); } pos += logits_bytes;
    size_t tend=pos+token_bytes; for(uint32_t i=0;i<r.vocab;i++){ if(pos+2>tend) throw reject("MALFORMED"); uint16_t L; std::memcpy(&L,mb.data+pos,2); pos+=2; if(pos+L>tend) throw reject("MALFORMED"); r.tokens.emplace_back(reinterpret_cast<char*>(mb.data+pos),L); pos+=L; } if(pos!=tend) throw reject("MALFORMED"); if(r.tokens[r.blank] != "_") throw reject("MALFORMED");
    size_t bend=pos+bias_bytes; if(pos+4>bend) throw reject("MALFORMED"); uint32_t bc=read_u32(mb.data+pos); pos+=4; for(uint32_t i=0;i<bc;i++){ if(pos+2>bend) throw reject("MALFORMED"); uint16_t L; std::memcpy(&L,mb.data+pos,2); pos+=2; if(pos+L+4>bend) throw reject("MALFORMED"); std::string phrase(reinterpret_cast<char*>(mb.data+pos),L); pos+=L; float w=read_f32(mb.data+pos); pos+=4; if(!std::isfinite(w)||std::fabs(w)>100) throw reject("MALFORMED"); r.biases.push_back({phrase,w}); } if(pos!=bend) throw reject("MALFORMED"); return r;
}
}

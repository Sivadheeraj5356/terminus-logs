namespace cb {
void write_response(Mailbox& mb,const std::string& body){ uint32_t n=std::min<uint32_t>(body.size(), kMailboxSize-kResponseOffset); std::memcpy(mb.data+kResponseOffset,body.data(),n); write_u32(mb.data+60,0); write_u32(mb.data+64,n); }
void write_error(Mailbox& mb,const std::string& code){ std::string body="{\"ok\":false,\"code\":\""+json_escape(code)+"\"}"; std::memcpy(mb.data+kResponseOffset,body.data(),body.size()); write_u32(mb.data+60,1); write_u32(mb.data+64,uint32_t(body.size())); }
std::string success_json(uint64_t id,const std::vector<Hypothesis>& hyps){ std::ostringstream o; o<<"{\"ok\":true,\"requestId\":"<<id<<",\"hypotheses\":["; for(size_t i=0;i<hyps.size();++i){ if(i)o<<","; o<<hypothesis_json(hyps[i]); } o<<"]}"; return o.str(); }
}

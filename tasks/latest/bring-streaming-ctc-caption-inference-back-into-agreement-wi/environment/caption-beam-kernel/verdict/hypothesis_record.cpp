namespace cb {
std::string hypothesis_json(const Hypothesis& h){ std::ostringstream o; o<<"{\"ids\":["; for(size_t i=0;i<h.ids.size();++i){ if(i)o<<","; o<<h.ids[i]; } o<<"],\"text\":\""<<json_escape(h.text)<<"\",\"acoustic\":"<<h.acoustic<<",\"bias\":"<<h.bias<<",\"total\":"<<h.total<<",\"confidence\":"<<h.confidence<<",\"spans\":["; for(size_t i=0;i<h.spans.size();++i){ if(i)o<<","; o<<"["<<h.spans[i].first<<","<<h.spans[i].second<<"]"; } o<<"]}"; return o.str(); }
}

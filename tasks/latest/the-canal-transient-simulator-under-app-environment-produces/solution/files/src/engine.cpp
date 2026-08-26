
#include "lockcore/engine.hpp"

#include <array>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <limits>
#include <regex>

namespace fs = std::filesystem;
namespace lockcore {

// -------------------- SHA-256 --------------------
namespace {

struct Sha256 {
    uint32_t state[8]{};
    uint64_t bitlen = 0;
    uint8_t data[64]{};
    size_t datalen = 0;

    Sha256() { reset(); }
    void reset() {
        state[0]=0x6a09e667; state[1]=0xbb67ae85; state[2]=0x3c6ef372; state[3]=0xa54ff53a;
        state[4]=0x510e527f; state[5]=0x9b05688c; state[6]=0x1f83d9ab; state[7]=0x5be0cd19;
        bitlen=0; datalen=0;
    }
    static uint32_t rotr(uint32_t x, uint32_t n){ return (x>>n)|(x<<(32-n)); }
    void transform() {
        static const uint32_t k[64]={
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
        uint32_t m[64];
        for(int i=0;i<16;++i)
            m[i]=(uint32_t(data[i*4])<<24)|(uint32_t(data[i*4+1])<<16)|(uint32_t(data[i*4+2])<<8)|uint32_t(data[i*4+3]);
        for(int i=16;i<64;++i){
            uint32_t s0=rotr(m[i-15],7)^rotr(m[i-15],18)^(m[i-15]>>3);
            uint32_t s1=rotr(m[i-2],17)^rotr(m[i-2],19)^(m[i-2]>>10);
            m[i]=m[i-16]+s0+m[i-7]+s1;
        }
        uint32_t a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
        for(int i=0;i<64;++i){
            uint32_t S1=rotr(e,6)^rotr(e,11)^rotr(e,25);
            uint32_t ch=(e&f)^((~e)&g);
            uint32_t t1=h+S1+ch+k[i]+m[i];
            uint32_t S0=rotr(a,2)^rotr(a,13)^rotr(a,22);
            uint32_t maj=(a&b)^(a&c)^(b&c);
            uint32_t t2=S0+maj;
            h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
    }
    void update(const uint8_t* d, size_t len){
        for(size_t i=0;i<len;++i){
            data[datalen++]=d[i];
            if(datalen==64){ transform(); bitlen+=512; datalen=0; }
        }
    }
    void update(const std::string& s){ update(reinterpret_cast<const uint8_t*>(s.data()), s.size()); }
    std::string final_hex(){
        bitlen += datalen*8;
        data[datalen++]=0x80;
        if(datalen>56){ while(datalen<64) data[datalen++]=0; transform(); datalen=0; }
        while(datalen<56) data[datalen++]=0;
        for(int i=7;i>=0;--i) data[datalen++] = uint8_t((bitlen>>(i*8))&0xff);
        transform();
        std::ostringstream oss;
        for(int i=0;i<8;++i) oss<<std::hex<<std::setw(8)<<std::setfill('0')<<state[i];
        return oss.str();
    }
};

} // anon

std::string sha256_hex(const std::string& data){
    Sha256 s; s.update(data); return s.final_hex();
}

std::string read_file(const std::string& path){
    std::ifstream in(path, std::ios::binary);
    if(!in) throw std::runtime_error("cannot open "+path);
    std::ostringstream ss; ss<<in.rdbuf();
    return ss.str();
}

void ensure_parent_dirs(const std::string& path){
    fs::path p(path);
    if(p.has_parent_path()) fs::create_directories(p.parent_path());
}

void write_atomic(const std::string& path, const std::string& content){
    ensure_parent_dirs(path);
    fs::path tmp = fs::path(path).parent_path() / (".tmp_"+fs::path(path).filename().string());
    {
        std::ofstream out(tmp, std::ios::binary);
        if(!out) throw std::runtime_error("cannot write temp");
        out<<content;
        out.flush();
    }
    fs::rename(tmp, path);
}

// -------------------- Minimal JSON (via Python-style: use regex/hand for our fixtures) --------------------
// For robustness we use a tiny recursive descent parser.

struct JVal {
    enum Type { Null, Bool, Number, String, Array, Object } type=Null;
    bool b=false; double n=0; std::string s; std::vector<JVal> a; std::vector<std::pair<std::string,JVal>> o;
    const JVal* get(const std::string& k) const {
        for(auto& kv:o) if(kv.first==k) return &kv.second;
        return nullptr;
    }
    const JVal& req(const std::string& k) const {
        auto* p=get(k); if(!p) throw std::runtime_error("missing key "+k); return *p;
    }
};

class JParse {
public:
    explicit JParse(const std::string& t): text(t) {}
    JVal parse(){ skip(); auto v=value(); skip(); if(i!=text.size()) throw std::runtime_error("trailing"); return v; }
private:
    std::string text; size_t i=0;
    void skip(){ while(i<text.size() && std::isspace((unsigned char)text[i])) ++i; }
    char peek(){ return i<text.size()? text[i]: '\0'; }
    char getc(){ return text[i++]; }
    JVal value(){
        skip();
        char c=peek();
        if(c=='{') return object();
        if(c=='[') return array();
        if(c=='"') return string();
        if(c=='t'||c=='f') return boolean();
        if(c=='n'){ if(text.substr(i,4)!="null") throw std::runtime_error("null"); i+=4; return JVal{}; }
        return number();
    }
    JVal object(){
        JVal v; v.type=JVal::Object; getc(); skip();
        if(peek()=='}'){ getc(); return v; }
        while(true){
            skip(); auto k=string(); skip(); if(getc()!=':') throw std::runtime_error(":");
            auto val=value(); v.o.push_back({k.s,val}); skip();
            char c=getc(); if(c=='}') break; if(c!=',') throw std::runtime_error(",");
        }
        return v;
    }
    JVal array(){
        JVal v; v.type=JVal::Array; getc(); skip();
        if(peek()==']'){ getc(); return v; }
        while(true){
            v.a.push_back(value()); skip();
            char c=getc(); if(c==']') break; if(c!=',') throw std::runtime_error(",");
        }
        return v;
    }
    JVal string(){
        if(getc()!='"') throw std::runtime_error("str");
        std::string s;
        while(true){
            char c=getc();
            if(c=='"') break;
            if(c=='\\'){ char e=getc(); if(e=='"'||e=='\\'||e=='/') s.push_back(e);
                else if(e=='n') s.push_back('\n'); else if(e=='t') s.push_back('\t');
                else throw std::runtime_error("escape"); }
            else s.push_back(c);
        }
        JVal v; v.type=JVal::String; v.s=s; return v;
    }
    JVal boolean(){
        JVal v; v.type=JVal::Bool;
        if(text.substr(i,4)=="true"){ i+=4; v.b=true; }
        else if(text.substr(i,5)=="false"){ i+=5; v.b=false; }
        else throw std::runtime_error("bool");
        return v;
    }
    JVal number(){
        size_t start=i;
        if(peek()=='-') ++i;
        while(std::isdigit((unsigned char)peek())) ++i;
        if(peek()=='.'){ ++i; while(std::isdigit((unsigned char)peek())) ++i; }
        if(peek()=='e'||peek()=='E'){ ++i; if(peek()=='+'||peek()=='-') ++i; while(std::isdigit((unsigned char)peek())) ++i; }
        JVal v; v.type=JVal::Number; v.n=std::stod(text.substr(start,i-start)); return v;
    }
};

static StorageCurve parse_curve(const JVal& arr){
    StorageCurve c;
    for(auto& k: arr.a){
        CurveKnot knot;
        knot.level_m = k.req("level_m").n;
        knot.volume_m3 = k.req("volume_m3").n;
        c.knots.push_back(knot);
    }
    return c;
}

CaseSpec load_case(const std::string& path){
    auto root = JParse(read_file(path)).parse();
    CaseSpec c;
    c.schema_version = int(root.req("schema_version").n);
    c.case_id = root.req("case_id").s;
    c.start_time_s = int64_t(root.req("start_time_s").n);
    c.end_time_s = int64_t(root.req("end_time_s").n);
    c.output_interval_s = int64_t(root.req("output_interval_s").n);
    c.topology_path = root.req("topology_path").s;
    c.forcing_path = root.req("forcing_path").s;
    auto& sol = root.req("solver");
    c.solver.initial_step_s = sol.req("initial_step_s").n;
    c.solver.minimum_step_s = sol.req("minimum_step_s").n;
    c.solver.maximum_step_s = sol.req("maximum_step_s").n;
    c.solver.volume_abs_tolerance_m3 = sol.req("volume_abs_tolerance_m3").n;
    c.solver.volume_rel_tolerance = sol.req("volume_rel_tolerance").n;
    c.solver.newton_abs_tolerance_m3 = sol.req("newton_abs_tolerance_m3").n;
    c.solver.newton_rel_tolerance = sol.req("newton_rel_tolerance").n;
    c.solver.maximum_newton_iterations = int(sol.req("maximum_newton_iterations").n);
    return c;
}

Topology load_topology(const std::string& path){
    auto root = JParse(read_file(path)).parse();
    Topology t;
    t.schema_version = int(root.req("schema_version").n);
    t.gravity_m_s2 = root.req("gravity_m_s2").n;
    for(auto& n: root.req("nodes").a){
        NodeSpec ns;
        ns.node_id = n.req("node_id").s;
        auto ty = n.req("node_type").s;
        ns.node_type = (ty=="storage")? NodeType::Storage : NodeType::Boundary;
        ns.initial_level_m = n.req("initial_level_m").n;
        if(ns.node_type==NodeType::Storage){
            ns.storage_curve_revision = int(n.req("storage_curve_revision").n);
            ns.storage_curve = parse_curve(n.req("storage_curve"));
        }
        t.nodes.push_back(ns);
    }
    for(auto& l: root.req("links").a){
        LinkSpec ls;
        ls.link_id = l.req("link_id").s;
        auto ty = l.req("link_type").s;
        if(ty=="gate") ls.link_type=LinkType::Gate;
        else if(ty=="weir") ls.link_type=LinkType::Weir;
        else ls.link_type=LinkType::Pump;
        ls.from_node = l.req("from_node").s;
        ls.to_node = l.req("to_node").s;
        ls.initial_control = l.req("initial_control").n;
        ls.maximum_abs_flow_m3_s = l.req("maximum_abs_flow_m3_s").n;
        if(ls.link_type==LinkType::Gate){
            ls.discharge_coefficient = l.req("discharge_coefficient").n;
            ls.area_m2 = l.req("area_m2").n;
        } else if(ls.link_type==LinkType::Weir){
            ls.discharge_coefficient = l.req("discharge_coefficient").n;
            ls.width_m = l.req("width_m").n;
            ls.crest_level_m = l.req("crest_level_m").n;
        }
        t.links.push_back(ls);
    }
    if(auto* ii=root.get("initial_inflows")){
        for(auto& x: ii->a){
            t.initial_inflows[x.req("node_id").s] = x.req("flow_m3_s").n;
        }
    }
    return t;
}

std::vector<ForcingEvent> load_forcing_from_bytes(const std::string& bytes){
    if(bytes.empty() || bytes.back()!='\n') throw std::runtime_error("forcing must end with newline");
    std::vector<ForcingEvent> evs;
    std::istringstream iss(bytes);
    std::string line;
    while(std::getline(iss,line)){
        if(line.empty()) throw std::runtime_error("empty forcing line");
        auto root = JParse(line).parse();
        ForcingEvent e;
        e.event_id = root.req("event_id").s;
        e.source_seq = int64_t(root.req("source_seq").n);
        e.time_s = int64_t(root.req("time_s").n);
        e.event_type = parse_event_type(root.req("event_type").s);
        if(auto* p=root.get("node_id")) e.node_id=p->s;
        if(auto* p=root.get("link_id")) e.link_id=p->s;
        if(auto* p=root.get("level_m")) e.level_m=p->n;
        if(auto* p=root.get("control")) e.control=p->n;
        if(auto* p=root.get("flow_m3_s")) e.flow_m3_s=p->n;
        if(auto* p=root.get("delta_volume_m3")) e.delta_volume_m3=p->n;
        if(auto* p=root.get("revision")) e.revision=int(p->n);
        if(auto* p=root.get("storage_curve")) e.storage_curve=parse_curve(*p);
        evs.push_back(e);
    }
    std::sort(evs.begin(), evs.end(), [](const ForcingEvent& a, const ForcingEvent& b){
        if (a.time_s != b.time_s) return a.time_s < b.time_s;
        if (event_type_rank(a.event_type) != event_type_rank(b.event_type))
            return event_type_rank(a.event_type) < event_type_rank(b.event_type);
        if (a.source_seq != b.source_seq) return a.source_seq < b.source_seq;
        return a.event_id < b.event_id;
    });
    return evs;
}

static std::string canon_num(double v){
    if(v==0.0) return "0";
    std::ostringstream oss; oss.setf(std::ios::fmtflags(0), std::ios::floatfield);
    oss<<std::setprecision(17)<<v;
    return oss.str();
}

std::string compute_case_digest(const CaseSpec& cas, const Topology& topo){
    std::ostringstream oss;
    oss<<"case|"<<cas.case_id<<"|"<<cas.start_time_s<<"|"<<cas.end_time_s<<"|"<<cas.output_interval_s<<"\n";
    oss<<"solver|"<<canon_num(cas.solver.initial_step_s)<<"|"<<canon_num(cas.solver.minimum_step_s)<<"|"
       <<canon_num(cas.solver.maximum_step_s)<<"|"<<canon_num(cas.solver.volume_abs_tolerance_m3)<<"|"
       <<canon_num(cas.solver.volume_rel_tolerance)<<"|"<<canon_num(cas.solver.newton_abs_tolerance_m3)<<"|"
       <<canon_num(cas.solver.newton_rel_tolerance)<<"|"<<cas.solver.maximum_newton_iterations<<"\n";
    auto nodes=topo.nodes; std::sort(nodes.begin(),nodes.end(),[](auto&a,auto&b){return a.node_id<b.node_id;});
    for(auto& n: nodes){
        oss<<"node|"<<n.node_id<<"|"<<(n.node_type==NodeType::Storage?"storage":"boundary")<<"|"<<canon_num(n.initial_level_m);
        if(n.node_type==NodeType::Storage){
            oss<<"|"<<n.storage_curve_revision;
            for(auto& k: n.storage_curve.knots) oss<<"|"<<canon_num(k.level_m)<<","<<canon_num(k.volume_m3);
        }
        oss<<"\n";
    }
    auto links=topo.links; std::sort(links.begin(),links.end(),[](auto&a,auto&b){return a.link_id<b.link_id;});
    for(auto& l: links){
        oss<<"link|"<<l.link_id<<"|"<<int(l.link_type)<<"|"<<l.from_node<<"|"<<l.to_node<<"|"
           <<canon_num(l.initial_control)<<"|"<<canon_num(l.maximum_abs_flow_m3_s)<<"|"
           <<canon_num(l.discharge_coefficient)<<"|"<<canon_num(l.area_m2)<<"|"<<canon_num(l.width_m)<<"|"
           <<canon_num(l.crest_level_m)<<"\n";
    }
    return sha256_hex(oss.str());
}

void init_sim(SimState& s, const CaseSpec& cas, const Topology& topo, const std::vector<ForcingEvent>& events,
              const std::string& forcing_bytes){
    s.cas=cas; s.topo=topo; s.events=events; s.forcing_bytes=forcing_bytes;
    s.case_digest_hex=compute_case_digest(cas,topo);
    s.time_s=cas.start_time_s;
    s.next_step_s=cas.solver.initial_step_s;
    s.diagnostics={};
    s.samples.clear();
    s.next_event_idx=0;
    s.processed_bytes=(int64_t)forcing_bytes.size();
    s.max_source_seq=0;
    s.storage_ids.clear(); s.boundary_ids.clear();
    s.volumes.clear(); s.boundary_levels.clear(); s.link_controls.clear();
    s.external_inflows.clear(); s.active_curves.clear(); s.curve_revisions.clear();
    s.node_by_id.clear(); s.link_by_id.clear();
    for(auto& n: s.topo.nodes){
        s.node_by_id[n.node_id]=&n;
        if(n.node_type==NodeType::Storage){
            s.storage_ids.push_back(n.node_id);
            s.active_curves[n.node_id]=n.storage_curve;
            s.curve_revisions[n.node_id]=n.storage_curve_revision;
            s.volumes[n.node_id]=volumeFromLevel(n.storage_curve, n.initial_level_m);
            s.external_inflows[n.node_id]=0.0;
        } else {
            s.boundary_ids.push_back(n.node_id);
            s.boundary_levels[n.node_id]=n.initial_level_m;
        }
    }
    std::sort(s.storage_ids.begin(), s.storage_ids.end());
    std::sort(s.boundary_ids.begin(), s.boundary_ids.end());
    for(size_t i=0;i<s.storage_ids.size();++i) s.node_index[s.storage_ids[i]]=i;
    for(auto& kv: topo.initial_inflows) s.external_inflows[kv.first]=kv.second;
    for(auto& l: s.topo.links){ s.link_by_id[l.link_id]=&l; s.link_controls[l.link_id]=l.initial_control; }
    double total=0; for(auto& id: s.storage_ids) total+=s.volumes[id];
    s.conservation.initial_total_storage_m3=total;
    s.conservation.cumulative_external_volume_m3=0.0;
}

static double level_of(const SimState& s, const std::string& id){
    if(s.volumes.count(id)) return levelFromVolume(s.active_curves.at(id), s.volumes.at(id));
    return s.boundary_levels.at(id);
}

static double eval_link_flow(const SimState& s, const LinkSpec& l, double h_from, double h_to){
    double ctrl=s.link_controls.at(l.link_id);
    if(l.link_type==LinkType::Gate)
        return gateFlow(h_from,h_to,ctrl,l.discharge_coefficient,l.area_m2,s.topo.gravity_m_s2,l.maximum_abs_flow_m3_s);
    if(l.link_type==LinkType::Weir)
        return weirFlow(h_from,h_to,ctrl,l.discharge_coefficient,l.width_m,l.crest_level_m,l.maximum_abs_flow_m3_s);
    return pumpFlow(ctrl, l.maximum_abs_flow_m3_s);
}

static std::vector<double> derivatives(const SimState& s, const std::vector<double>& V){
    std::map<std::string,double> vol;
    for(size_t i=0;i<s.storage_ids.size();++i) vol[s.storage_ids[i]]=V[i];
    std::map<std::string,double> levels=s.boundary_levels;
    for(auto& id: s.storage_ids) levels[id]=levelFromVolume(s.active_curves.at(id), vol.at(id));
    std::vector<double> dV(s.storage_ids.size(),0.0);
    for(size_t i=0;i<s.storage_ids.size();++i) dV[i]+=s.external_inflows.at(s.storage_ids[i]);
    for(auto& l: s.topo.links){
        double q=eval_link_flow(s,l,levels.at(l.from_node),levels.at(l.to_node));
        auto add=[&](const std::string& node, double sign){
            if(s.node_index.count(node)) dV[s.node_index.at(node)] += sign*q;
        };
        // flow from->to : from loses, to gains
        add(l.from_node, -1.0);
        add(l.to_node, +1.0);
    }
    return dV;
}

static bool volumes_in_curve(const SimState& s, const std::vector<double>& V){
    for(size_t i=0;i<s.storage_ids.size();++i)
        if(!curveContainsVolume(s.active_curves.at(s.storage_ids[i]), V[i])) return false;
    return true;
}

static double inf_norm(const std::vector<double>& v){
    double m=0; for(double x:v) m=std::max(m,std::fabs(x)); return m;
}

static bool implicit_midpoint(SimState& s, double dt, const std::vector<double>& V0,
                              std::vector<double>& V1, std::vector<double>& mid_flows, int& newton_iters){
    const size_t n=V0.size();
    auto f0=derivatives(s,V0);
    V1=V0;
    for(size_t i=0;i<n;++i) V1[i]=V0[i]+dt*f0[i];
    for(size_t i=0;i<n;++i){
        auto [lo,hi]=volumeRange(s.active_curves.at(s.storage_ids[i]));
        if(V1[i]<lo) V1[i]=lo; if(V1[i]>hi) V1[i]=hi;
    }
    newton_iters=0;
    for(int it=0; it<s.cas.solver.maximum_newton_iterations; ++it){
        std::vector<double> Vmid(n);
        for(size_t i=0;i<n;++i) Vmid[i]=0.5*(V0[i]+V1[i]);
        if(!volumes_in_curve(s,Vmid)) return false;
        auto fmid=derivatives(s,Vmid);
        std::vector<double> F(n);
        for(size_t i=0;i<n;++i) F[i]=V1[i]-V0[i]-dt*fmid[i];
        double tol=s.cas.solver.newton_abs_tolerance_m3 + s.cas.solver.newton_rel_tolerance*std::max(1.0, inf_norm(V1));
        if(inf_norm(F)<=tol){
            // midpoint flows for conservation
            mid_flows.assign(s.topo.links.size(),0.0);
            std::map<std::string,double> levels=s.boundary_levels;
            for(size_t i=0;i<n;++i) levels[s.storage_ids[i]]=levelFromVolume(s.active_curves.at(s.storage_ids[i]), Vmid[i]);
            for(size_t li=0; li<s.topo.links.size(); ++li){
                auto& l=s.topo.links[li];
                mid_flows[li]=eval_link_flow(s,l,levels.at(l.from_node),levels.at(l.to_node));
            }
            return true;
        }
        ++newton_iters;
        // FD Jacobian of f w.r.t Vmid
        std::vector<std::vector<double>> df(n, std::vector<double>(n,0.0));
        for(size_t j=0;j<n;++j){
            double eps=std::max(1e-8, 1e-7*std::max(1.0,std::fabs(Vmid[j])));
            auto Vp=Vmid, Vm=Vmid;
            bool can_p=true, can_m=true;
            Vp[j]+=eps; Vm[j]-=eps;
            if(!volumes_in_curve(s,Vp)) can_p=false;
            if(!volumes_in_curve(s,Vm)) can_m=false;
            if(!can_p && !can_m) return false;
            std::vector<double> col(n);
            if(can_p && can_m){
                auto fp=derivatives(s,Vp), fm=derivatives(s,Vm);
                for(size_t i=0;i<n;++i) col[i]=(fp[i]-fm[i])/(2*eps);
            } else if(can_p){
                auto fp=derivatives(s,Vp), f0=derivatives(s,Vmid);
                for(size_t i=0;i<n;++i) col[i]=(fp[i]-f0[i])/eps;
            } else {
                auto fm=derivatives(s,Vm), f0=derivatives(s,Vmid);
                for(size_t i=0;i<n;++i) col[i]=(f0[i]-fm[i])/eps;
            }
            for(size_t i=0;i<n;++i) df[i][j]=col[i];
        }
        // J = I - (dt/2) df
        std::vector<std::vector<double>> J(n, std::vector<double>(n,0.0));
        std::vector<double> rhs(n);
        for(size_t i=0;i<n;++i){
            for(size_t j=0;j<n;++j) J[i][j] = ((i==j)?1.0:0.0) - 0.5*dt*df[i][j];
            rhs[i]=-F[i];
        }
        // GE with partial pivoting
        for(size_t col=0; col<n; ++col){
            size_t piv=col; double best=std::fabs(J[col][col]);
            for(size_t r=col+1;r<n;++r){
                double a=std::fabs(J[r][col]);
                if(a > best || (a == best && r < piv)){ best=a; piv=r; }
            }
            if(best<1e-14) return false;
            if(piv!=col){ std::swap(J[piv],J[col]); std::swap(rhs[piv],rhs[col]); }
            for(size_t r=col+1;r<n;++r){
                double f=J[r][col]/J[col][col];
                for(size_t c=col;c<n;++c) J[r][c]-=f*J[col][c];
                rhs[r]-=f*rhs[col];
            }
        }
        std::vector<double> delta(n);
        for(int i=int(n)-1;i>=0;--i){
            double sum=rhs[i];
            for(size_t c=i+1;c<n;++c) sum-=J[i][c]*delta[c];
            delta[i]=sum/J[i][i];
        }
        // Damped line search (starter omits residual-decrease check in soft form).
        double alpha = 1.0;
        bool accepted = false;
        double prev_res = inf_norm(F);
        for(int k=0;k<8;++k){
            std::vector<double> trial=V1;
            for(size_t i=0;i<n;++i) trial[i]+=alpha*delta[i];
            if(volumes_in_curve(s,trial)){
                std::vector<double> Vmid2(n);
                for(size_t i=0;i<n;++i) Vmid2[i]=0.5*(V0[i]+trial[i]);
                if(volumes_in_curve(s,Vmid2)){
                    auto f2=derivatives(s,Vmid2);
                    std::vector<double> F2(n);
                    for(size_t i=0;i<n;++i) F2[i]=trial[i]-V0[i]-dt*f2[i];
                    if(inf_norm(F2) < prev_res){
                        V1=trial;
                        accepted=true;
                        break;
                    }
                }
            }
            alpha *= 0.5;
        }
        if(!accepted) return false;
    }
    return false;
}

static void accumulate_external(SimState& s, double half_dt, const std::vector<double>& mid_flows){
    double ext=0.0;
    for(auto& id: s.storage_ids) ext += s.external_inflows.at(id);
    for(size_t li=0; li<s.topo.links.size(); ++li){
        const auto& l = s.topo.links[li];
        bool from_storage = s.node_index.count(l.from_node) > 0;
        bool to_storage = s.node_index.count(l.to_node) > 0;
        double q = mid_flows[li];
        if(from_storage && !to_storage) ext -= q; // leaving network
        if(!from_storage && to_storage) ext += q; // entering network
    }
    s.conservation.cumulative_external_volume_m3 += half_dt * ext;
}

bool integrate_to(SimState& s, int64_t target_time){
    double t = static_cast<double>(s.time_s);
    const double t_end = static_cast<double>(target_time);
    while(t + 1e-12 < t_end){
        double dt = s.next_step_s;
        double remain = t_end - t;
        if(dt > remain) dt = remain;
        if(dt <= 0) break;

        std::vector<double> V0;
        for(auto& id: s.storage_ids) V0.push_back(s.volumes[id]);
        const size_t n = V0.size();
        const double half = 0.5 * dt;

        std::vector<double> V_full, flows_full;
        std::vector<double> V_half, flows_half;
        std::vector<double> V_half2, flows_half2;
        int nit_full = 0, nit_half = 0, nit_half2 = 0;

        bool ok_full = implicit_midpoint(s, dt, V0, V_full, flows_full, nit_full);
        s.diagnostics.newton_iterations += nit_full;

        bool ok_half = false;
        bool ok_half2 = false;
        if(ok_full){
            ok_half = implicit_midpoint(s, half, V0, V_half, flows_half, nit_half);
            s.diagnostics.newton_iterations += nit_half;
        }
        if(ok_full && ok_half){
            ok_half2 = implicit_midpoint(s, half, V_half, V_half2, flows_half2, nit_half2);
            s.diagnostics.newton_iterations += nit_half2;
        }

        bool reject = !(ok_full && ok_half && ok_half2);
        double error = 0.0;
        if(!reject){
            if(n == 0){
                error = 0.0;
            } else {
                for(size_t i = 0; i < n; ++i){
                    double scale = s.cas.solver.volume_abs_tolerance_m3
                        + s.cas.solver.volume_rel_tolerance
                          * std::max(1.0, std::max(std::fabs(V_full[i]), std::fabs(V_half2[i])));
                    error = std::max(error, std::fabs(V_half2[i] - V_full[i]) / scale);
                }
            }
            if(error > 1.0) reject = true;
        }

        if(reject){
            // One rejected candidate attempt, regardless of how many midpoint solves failed.
            s.diagnostics.rejected_attempts += 1;
            double ndt = dt * 0.5;
            if(ndt + 1e-12 < s.cas.solver.minimum_step_s) throw std::runtime_error("min step failure");
            s.next_step_s = ndt;
            continue;
        }

        // Commit the two-half-step solution; never V_full / Richardson.
        for(size_t i = 0; i < n; ++i) s.volumes[s.storage_ids[i]] = V_half2[i];
        accumulate_external(s, half, flows_half);
        accumulate_external(s, half, flows_half2);
        t += dt;
        s.time_s = static_cast<int64_t>(std::llround(t));
        s.diagnostics.accepted_substeps += 2;
        s.diagnostics.minimum_accepted_step_s = (s.diagnostics.minimum_accepted_step_s==0)? dt : std::min(s.diagnostics.minimum_accepted_step_s, dt);
        s.diagnostics.maximum_accepted_step_s = std::max(s.diagnostics.maximum_accepted_step_s, dt);
        if(error < 0.0625){
            s.next_step_s = std::min(2.0 * dt, s.cas.solver.maximum_step_s);
        } else if(error > 0.5){
            s.next_step_s = std::max(dt / 2.0, s.cas.solver.minimum_step_s);
        } else {
            s.next_step_s = dt;
        }
    }
    s.time_s = target_time;
    return true;
}

void apply_events_at(SimState& s, int64_t t){
    for(auto& e: s.events){
        if(e.time_s != t) continue;
        if(e.source_seq <= s.max_source_seq) continue;
        if(e.event_type==EventType::ExternalInflow){
            s.external_inflows[e.node_id]=e.flow_m3_s;
        } else if(e.event_type==EventType::BoundaryStage){
            s.boundary_levels[e.node_id]=e.level_m;
        } else if(e.event_type==EventType::LinkControl){
            s.link_controls[e.link_id]=e.control;
        } else if(e.event_type==EventType::VolumeImpulse){
            s.volumes[e.node_id]+=e.delta_volume_m3;
            s.conservation.cumulative_external_volume_m3 += e.delta_volume_m3;
            if(!curveContainsVolume(s.active_curves[e.node_id], s.volumes[e.node_id]))
                throw std::runtime_error("impulse out of range");
        } else if(e.event_type==EventType::StorageCurveRevision){
            s.active_curves[e.node_id]=e.storage_curve;
            s.curve_revisions[e.node_id]=e.revision;
            if(!curveContainsVolume(s.active_curves[e.node_id], s.volumes[e.node_id]))
                throw std::runtime_error("revision out of range");
        }
        s.max_source_seq = std::max(s.max_source_seq, e.source_seq);
    }
}

Sample take_sample(SimState& s, int64_t t){
    Sample sm; sm.time_s=t;
    double total=0;
    for(auto& id: s.storage_ids){
        NodeSample ns;
        ns.node_id=id; ns.node_type="storage";
        ns.curve_revision=s.curve_revisions[id];
        ns.volume_m3=round_half_even(s.volumes[id],9);
        ns.level_m=round_half_even(levelFromVolume(s.active_curves[id], s.volumes[id]),9);
        total += s.volumes[id];
        sm.nodes.push_back(ns);
    }
    for(auto& id: s.boundary_ids){
        NodeSample ns; ns.node_id=id; ns.node_type="boundary";
        ns.level_m=round_half_even(s.boundary_levels[id],9);
        sm.nodes.push_back(ns);
    }
    std::sort(sm.nodes.begin(), sm.nodes.end(), [](auto&a,auto&b){return a.node_id<b.node_id;});
    std::map<std::string,double> levels=s.boundary_levels;
    for(auto& id: s.storage_ids) levels[id]=levelFromVolume(s.active_curves[id], s.volumes[id]);
    for(auto& l: s.topo.links){
        LinkSample ls;
        ls.link_id=l.link_id;
        ls.link_type = (l.link_type==LinkType::Gate)?"gate":(l.link_type==LinkType::Weir)?"weir":"pump";
        ls.control=round_half_even(s.link_controls[l.link_id],9);
        ls.flow_m3_s=round_half_even(eval_link_flow(s,l,levels[l.from_node],levels[l.to_node]),9);
        sm.links.push_back(ls);
    }
    std::sort(sm.links.begin(), sm.links.end(), [](auto&a,auto&b){return a.link_id<b.link_id;});
    double residual = total - s.conservation.initial_total_storage_m3 - s.conservation.cumulative_external_volume_m3;
    s.diagnostics.maximum_abs_mass_residual_m3 = std::max(s.diagnostics.maximum_abs_mass_residual_m3, std::fabs(residual));
    sm.conservation.current_total_storage_m3=round_half_even(total,9);
    sm.conservation.cumulative_external_volume_m3=round_half_even(s.conservation.cumulative_external_volume_m3,9);
    sm.conservation.mass_residual_m3=round_half_even(residual,12);
    return sm;
}

static std::string json_escape(const std::string& s){
    std::ostringstream o; o<<'"';
    for(char c:s){ if(c=='"'||c=='\\') o<<'\\'<<c; else o<<c; }
    o<<'"'; return o.str();
}

TransientReport build_report(SimState& s, bool completed){
    TransientReport r;
    r.schema_version=4;
    r.case_id=s.cas.case_id;
    r.case_digest_hex=s.case_digest_hex;
    r.completed=completed;
    r.simulated_until_s=s.time_s;
    r.samples=s.samples;
    r.diagnostics=s.diagnostics;
    r.diagnostics.minimum_accepted_step_s=round_half_even(r.diagnostics.minimum_accepted_step_s,9);
    r.diagnostics.maximum_accepted_step_s=round_half_even(r.diagnostics.maximum_accepted_step_s,9);
    r.diagnostics.maximum_abs_mass_residual_m3=round_half_even(r.diagnostics.maximum_abs_mass_residual_m3,12);
    return r;
}

std::string serialize_report(const TransientReport& r){
    std::ostringstream o;
    o<<"{\"schema_version\":"<<r.schema_version
     <<",\"case_id\":"<<json_escape(r.case_id)
     <<",\"case_digest_hex\":"<<json_escape(r.case_digest_hex)
     <<",\"completed\":"<<(r.completed?"true":"false")
     <<",\"simulated_until_s\":"<<r.simulated_until_s
     <<",\"samples\":[";
    for(size_t si=0; si<r.samples.size(); ++si){
        auto& sm=r.samples[si];
        if(si) o<<",";
        o<<"{\"time_s\":"<<sm.time_s<<",\"nodes\":[";
        for(size_t i=0;i<sm.nodes.size();++i){
            auto& n=sm.nodes[i]; if(i) o<<",";
            o<<"{\"node_id\":"<<json_escape(n.node_id)<<",\"node_type\":"<<json_escape(n.node_type);
            if(n.node_type=="storage"){
                o<<",\"curve_revision\":"<<n.curve_revision
                 <<",\"level_m\":"<<n.level_m<<",\"volume_m3\":"<<n.volume_m3;
            } else {
                o<<",\"level_m\":"<<n.level_m;
            }
            o<<"}";
        }
        o<<"],\"links\":[";
        for(size_t i=0;i<sm.links.size();++i){
            auto& l=sm.links[i]; if(i) o<<",";
            o<<"{\"link_id\":"<<json_escape(l.link_id)<<",\"link_type\":"<<json_escape(l.link_type)
             <<",\"flow_m3_s\":"<<l.flow_m3_s<<",\"control\":"<<l.control<<"}";
        }
        o<<"],\"conservation\":{\"current_total_storage_m3\":"<<sm.conservation.current_total_storage_m3
         <<",\"cumulative_external_volume_m3\":"<<sm.conservation.cumulative_external_volume_m3
         <<",\"mass_residual_m3\":"<<sm.conservation.mass_residual_m3<<"}}";
    }
    o<<"],\"diagnostics\":{"
     <<"\"accepted_substeps\":"<<r.diagnostics.accepted_substeps
     <<",\"rejected_attempts\":"<<r.diagnostics.rejected_attempts
     <<",\"newton_iterations\":"<<r.diagnostics.newton_iterations
     <<",\"minimum_accepted_step_s\":"<<r.diagnostics.minimum_accepted_step_s
     <<",\"maximum_accepted_step_s\":"<<r.diagnostics.maximum_accepted_step_s
     <<",\"maximum_abs_mass_residual_m3\":"<<r.diagnostics.maximum_abs_mass_residual_m3
     <<"}";
    // audit digest over body without audit field
    std::string body = o.str() + "}";
    std::string dig = sha256_hex(body);
    // rebuild with digest
    std::ostringstream out;
    out<<o.str()<<",\"audit_digest_hex\":"<<json_escape(dig)<<"}\n";
    return out.str();
}

static void write_full(std::ostream& o, double v){
    if(v==0.0){ o<<'0'; return; }
    o<<std::setprecision(17)<<v;
}

static void write_sample_json(std::ostream& o, const Sample& sm){
    o<<"{\"time_s\":"<<sm.time_s<<",\"nodes\":[";
    for(size_t i=0;i<sm.nodes.size();++i){
        auto& n=sm.nodes[i]; if(i) o<<",";
        o<<"{\"node_id\":"<<json_escape(n.node_id)<<",\"node_type\":"<<json_escape(n.node_type);
        if(n.node_type=="storage"){
            o<<",\"curve_revision\":"<<n.curve_revision
             <<",\"level_m\":"<<n.level_m<<",\"volume_m3\":"<<n.volume_m3;
        } else {
            o<<",\"level_m\":"<<n.level_m;
        }
        o<<"}";
    }
    o<<"],\"links\":[";
    for(size_t i=0;i<sm.links.size();++i){
        auto& l=sm.links[i]; if(i) o<<",";
        o<<"{\"link_id\":"<<json_escape(l.link_id)<<",\"link_type\":"<<json_escape(l.link_type)
         <<",\"flow_m3_s\":"<<l.flow_m3_s<<",\"control\":"<<l.control<<"}";
    }
    o<<"],\"conservation\":{\"current_total_storage_m3\":"<<sm.conservation.current_total_storage_m3
     <<",\"cumulative_external_volume_m3\":"<<sm.conservation.cumulative_external_volume_m3
     <<",\"mass_residual_m3\":"<<sm.conservation.mass_residual_m3<<"}}";
}

static Sample parse_sample_json(const JVal& smj){
    Sample sm;
    sm.time_s = int64_t(smj.req("time_s").n);
    for(auto& nj: smj.req("nodes").a){
        NodeSample ns;
        ns.node_id = nj.req("node_id").s;
        ns.node_type = nj.req("node_type").s;
        ns.level_m = nj.req("level_m").n;
        if(ns.node_type=="storage"){
            ns.curve_revision = int(nj.req("curve_revision").n);
            ns.volume_m3 = nj.req("volume_m3").n;
        }
        sm.nodes.push_back(ns);
    }
    for(auto& lj: smj.req("links").a){
        LinkSample ls;
        ls.link_id = lj.req("link_id").s;
        ls.link_type = lj.req("link_type").s;
        ls.flow_m3_s = lj.req("flow_m3_s").n;
        ls.control = lj.req("control").n;
        sm.links.push_back(ls);
    }
    auto& cj = smj.req("conservation");
    sm.conservation.current_total_storage_m3 = cj.req("current_total_storage_m3").n;
    sm.conservation.cumulative_external_volume_m3 = cj.req("cumulative_external_volume_m3").n;
    sm.conservation.mass_residual_m3 = cj.req("mass_residual_m3").n;
    return sm;
}

static void verify_snapshot_digest(const std::string& text){
    auto pos = text.find(",\"snapshot_digest_hex\":");
    if(pos==std::string::npos) throw std::runtime_error("snapshot digest missing");
    std::string claimed;
    {
        auto root = JParse(text).parse();
        claimed = root.req("snapshot_digest_hex").s;
    }
    std::string material = text.substr(0, pos) + "}";
    if(sha256_hex(material) != claimed) throw std::runtime_error("snapshot digest mismatch");
}

static void validate_forcing_continuation(const SimState& s){
    const int64_t processed = s.processed_bytes;
    if(processed < 0) throw std::runtime_error("invalid processed_bytes");
    if((int64_t)s.forcing_bytes.size() < processed) throw std::runtime_error("forcing truncated");
    if(processed > 0){
        if(s.forcing_bytes[size_t(processed-1)] != '\n')
            throw std::runtime_error("processed_bytes not on line boundary");
    }
    size_t off = 0;
    while(off < s.forcing_bytes.size()){
        size_t nl = s.forcing_bytes.find('\n', off);
        if(nl == std::string::npos) throw std::runtime_error("forcing missing newline");
        size_t end = nl + 1;
        std::string line = s.forcing_bytes.substr(off, nl - off);
        if(line.empty()) throw std::runtime_error("empty forcing line");
        auto root = JParse(line).parse();
        int64_t seq = int64_t(root.req("source_seq").n);
        int64_t time_s = int64_t(root.req("time_s").n);
        if((int64_t)end > processed){
            if(seq <= s.max_source_seq) throw std::runtime_error("appended source_seq not greater than snapshot max");
            if(time_s <= s.time_s) throw std::runtime_error("appended time_s not greater than snapshot time");
        }
        off = end;
    }
}

std::string serialize_snapshot(const SimState& s){
    std::ostringstream o;
    o<<"{\"schema_version\":4,\"case_digest_hex\":"<<json_escape(s.case_digest_hex)
     <<",\"forcing_cursor\":{\"processed_bytes\":"<<s.processed_bytes
     <<",\"prefix_sha256\":"<<json_escape(sha256_hex(s.forcing_bytes.substr(0, size_t(s.processed_bytes))))
     <<",\"maximum_source_seq\":"<<s.max_source_seq
     <<"},\"simulated_until_s\":"<<s.time_s
     <<",\"storage_state\":[";
    for(size_t i=0;i<s.storage_ids.size();++i){
        if(i) o<<",";
        o<<"{\"node_id\":"<<json_escape(s.storage_ids[i])<<",\"volume_m3\":";
        write_full(o, s.volumes.at(s.storage_ids[i]));
        o<<"}";
    }
    o<<"],\"boundary_levels\":[";
    for(size_t i=0;i<s.boundary_ids.size();++i){
        if(i) o<<",";
        o<<"{\"node_id\":"<<json_escape(s.boundary_ids[i])<<",\"level_m\":";
        write_full(o, s.boundary_levels.at(s.boundary_ids[i]));
        o<<"}";
    }
    o<<"],\"link_controls\":[";
    bool first=true; for(auto& l: s.topo.links){ if(!first)o<<","; first=false;
        o<<"{\"link_id\":"<<json_escape(l.link_id)<<",\"control\":";
        write_full(o, s.link_controls.at(l.link_id));
        o<<"}"; }
    o<<"],\"external_inflows\":[";
    first=true; for(auto& id: s.storage_ids){ if(!first)o<<","; first=false;
        o<<"{\"node_id\":"<<json_escape(id)<<",\"flow_m3_s\":";
        write_full(o, s.external_inflows.at(id));
        o<<"}"; }
    o<<"],\"active_curves\":[";
    first=true; for(auto& id: s.storage_ids){ if(!first)o<<","; first=false;
        o<<"{\"node_id\":"<<json_escape(id)<<",\"revision\":"<<s.curve_revisions.at(id)<<",\"storage_curve\":[";
        auto& c=s.active_curves.at(id);
        for(size_t k=0;k<c.knots.size();++k){ if(k)o<<",";
            o<<"{\"level_m\":"; write_full(o, c.knots[k].level_m);
            o<<",\"volume_m3\":"; write_full(o, c.knots[k].volume_m3); o<<"}"; }
        o<<"]}"; }
    o<<"],\"prior_samples\":[";
    for(size_t i=0;i<s.samples.size();++i){
        if(i) o<<",";
        write_sample_json(o, s.samples[i]);
    }
    o<<"],\"solver_state\":{"
     <<"\"next_step_s\":"; write_full(o, s.next_step_s);
    o<<",\"accepted_substeps\":"<<s.diagnostics.accepted_substeps
     <<",\"rejected_attempts\":"<<s.diagnostics.rejected_attempts
     <<",\"newton_iterations\":"<<s.diagnostics.newton_iterations
     <<",\"minimum_accepted_step_s\":"; write_full(o, s.diagnostics.minimum_accepted_step_s);
    o<<",\"maximum_accepted_step_s\":"; write_full(o, s.diagnostics.maximum_accepted_step_s);
    o<<",\"maximum_abs_mass_residual_m3\":"; write_full(o, s.diagnostics.maximum_abs_mass_residual_m3);
    o<<"},\"conservation_state\":{"
     <<"\"initial_total_storage_m3\":"; write_full(o, s.conservation.initial_total_storage_m3);
    o<<",\"cumulative_external_volume_m3\":"; write_full(o, s.conservation.cumulative_external_volume_m3);
    o<<"}";
    std::string body=o.str()+"}";
    std::string dig=sha256_hex(body);
    return o.str()+",\"snapshot_digest_hex\":"+json_escape(dig)+"}\n";
}

void load_snapshot_into(SimState& s, const std::string& path){
    std::string text = read_file(path);
    verify_snapshot_digest(text);
    auto root=JParse(text).parse();
    auto& cursor = root.req("forcing_cursor");
    int64_t processed = int64_t(cursor.req("processed_bytes").n);
    std::string expected_prefix = cursor.req("prefix_sha256").s;
    if((int64_t)s.forcing_bytes.size() < processed) throw std::runtime_error("forcing truncated");
    std::string prefix = s.forcing_bytes.substr(0, size_t(processed));
    if(sha256_hex(prefix) != expected_prefix) throw std::runtime_error("forcing prefix hash mismatch");
    if(root.req("case_digest_hex").s != s.case_digest_hex) throw std::runtime_error("case digest mismatch");
    s.time_s = int64_t(root.req("simulated_until_s").n);
    s.processed_bytes = processed;
    s.max_source_seq = int64_t(cursor.req("maximum_source_seq").n);
    validate_forcing_continuation(s);
    for(auto& st: root.req("storage_state").a){
        s.volumes[st.req("node_id").s]=st.req("volume_m3").n;
    }
    for(auto& bl: root.req("boundary_levels").a){
        s.boundary_levels[bl.req("node_id").s]=bl.req("level_m").n;
    }
    for(auto& lc: root.req("link_controls").a){
        s.link_controls[lc.req("link_id").s]=lc.req("control").n;
    }
    for(auto& ei: root.req("external_inflows").a){
        s.external_inflows[ei.req("node_id").s]=ei.req("flow_m3_s").n;
    }
    for(auto& ac: root.req("active_curves").a){
        std::string id = ac.req("node_id").s;
        s.curve_revisions[id] = int(ac.req("revision").n);
        s.active_curves[id] = parse_curve(ac.req("storage_curve"));
    }
    auto& ss = root.req("solver_state");
    s.next_step_s = ss.req("next_step_s").n;
    s.diagnostics.accepted_substeps = int64_t(ss.req("accepted_substeps").n);
    s.diagnostics.rejected_attempts = int64_t(ss.req("rejected_attempts").n);
    s.diagnostics.newton_iterations = int64_t(ss.req("newton_iterations").n);
    s.diagnostics.minimum_accepted_step_s = ss.req("minimum_accepted_step_s").n;
    s.diagnostics.maximum_accepted_step_s = ss.req("maximum_accepted_step_s").n;
    s.diagnostics.maximum_abs_mass_residual_m3 = ss.req("maximum_abs_mass_residual_m3").n;
    auto& cs = root.req("conservation_state");
    s.conservation.initial_total_storage_m3 = cs.req("initial_total_storage_m3").n;
    s.conservation.cumulative_external_volume_m3 = cs.req("cumulative_external_volume_m3").n;
    s.samples.clear();
    for(auto& smj: root.req("prior_samples").a){
        s.samples.push_back(parse_sample_json(smj));
    }
}

static void run_simulation(SimState& s, int64_t stop_at, bool completed_expected){
    // collect sample times
    std::vector<int64_t> samples;
    for(int64_t t=s.cas.start_time_s; t<=stop_at; t+=s.cas.output_interval_s) samples.push_back(t);
    if(samples.empty() || samples.back()!=stop_at) samples.push_back(stop_at);
    // also include event times that are sample-aligned handled via apply before sample
    apply_events_at(s, s.time_s);
    if(s.time_s==s.cas.start_time_s){
        s.samples.push_back(take_sample(s, s.time_s));
    }
    for(size_t i=0;i<samples.size();++i){
        int64_t t=samples[i];
        if(t<=s.time_s) continue;
        // integrate through intermediate event times
        std::vector<int64_t> bounds;
        for(auto& e: s.events) if(e.time_s>s.time_s && e.time_s<=t) bounds.push_back(e.time_s);
        bounds.push_back(t);
        std::sort(bounds.begin(), bounds.end());
        bounds.erase(std::unique(bounds.begin(),bounds.end()), bounds.end());
        for(int64_t b: bounds){
            if(b>s.time_s) integrate_to(s,b);
            apply_events_at(s,b);
            if(b==t || (b%s.cas.output_interval_s==0 && b>=s.cas.start_time_s && b<=stop_at)){
                // emit if sample time
                bool is_sample=false;
                for(int64_t st: samples) if(st==b) is_sample=true;
                if(is_sample){
                    // avoid duplicate
                    if(s.samples.empty() || s.samples.back().time_s!=b)
                        s.samples.push_back(take_sample(s,b));
                }
            }
        }
    }
    (void)completed_expected;
}

int run_cli(int argc, char** argv){
    try{
        if(argc<2){ std::cerr<<"usage\n"; return 2; }
        std::string cmd=argv[1];
        if(cmd=="--help" || cmd=="-h"){
            std::cout<<"lockctl run|restore|audit\n"
                     <<"  --case --output --snapshot --snapshot-out --stop-at --ledger\n";
            return 0;
        }
        std::map<std::string,std::string> args;
        for(int i=2;i<argc;++i){
            std::string a=argv[i];
            if(a.rfind("--",0)!=0) throw std::runtime_error("unexpected positional");
            if(i+1>=argc) throw std::runtime_error("missing value");
            args[a]=argv[++i];
        }
        auto need=[&](const char* k){ if(!args.count(k)) throw std::runtime_error(std::string("missing ")+k); return args[k]; };
        auto abs_check=[&](const std::string& p){ if(p.empty()||p[0]!='/') throw std::runtime_error("paths must be absolute"); };

        if(cmd=="run"){
            auto case_path=need("--case"); abs_check(case_path);
            auto out_path=need("--output"); abs_check(out_path);
            auto cas=load_case(case_path);
            auto topo=load_topology(cas.topology_path);
            auto fbytes=read_file(cas.forcing_path);
            auto evs=load_forcing_from_bytes(fbytes);
            SimState s; init_sim(s,cas,topo,evs,fbytes);
            int64_t stop=cas.end_time_s;
            bool partial=false;
            if(args.count("--stop-at")){ stop=std::stoll(args["--stop-at"]); partial=true; }
            run_simulation(s, stop, !partial);
            auto rep=build_report(s, !partial);
            auto text=serialize_report(rep);
            if(args.count("--snapshot-out")){
                abs_check(args["--snapshot-out"]);
                write_atomic(out_path, text);
                write_atomic(args["--snapshot-out"], serialize_snapshot(s));
            } else {
                write_atomic(out_path, text);
            }
            return 0;
        }
        if(cmd=="restore"){
            auto case_path=need("--case"); abs_check(case_path);
            auto snap=need("--snapshot"); abs_check(snap);
            auto out_path=need("--output"); abs_check(out_path);
            auto cas=load_case(case_path);
            auto topo=load_topology(cas.topology_path);
            auto fbytes=read_file(cas.forcing_path);
            auto evs=load_forcing_from_bytes(fbytes);
            SimState s; init_sim(s,cas,topo,evs,fbytes);
            load_snapshot_into(s, snap);
            int64_t stop=cas.end_time_s;
            if(args.count("--stop-at")) stop=std::stoll(args["--stop-at"]);
            run_simulation(s, stop, stop==cas.end_time_s);
            write_atomic(out_path, serialize_report(build_report(s, stop==cas.end_time_s)));
            return 0;
        }
        if(cmd=="audit"){
            auto case_path=need("--case"); abs_check(case_path);
            auto ledger=need("--ledger"); abs_check(ledger);
            auto cas=load_case(case_path);
            auto topo=load_topology(cas.topology_path);
            auto fbytes=read_file(cas.forcing_path);
            auto evs=load_forcing_from_bytes(fbytes);
            SimState s; init_sim(s,cas,topo,evs,fbytes);
            run_simulation(s, cas.end_time_s, true);
            auto fresh=serialize_report(build_report(s,true));
            auto existing=read_file(ledger);
            auto fj=JParse(fresh).parse();
            auto ej=JParse(existing).parse();
            bool ok = fj.req("samples").a.size()==ej.req("samples").a.size();
            if(ok){
                for(size_t i=0;i<fj.req("samples").a.size();++i){
                    auto& fc=fj.req("samples").a[i].req("conservation");
                    auto& ec=ej.req("samples").a[i].req("conservation");
                    for(const char* k: {"current_total_storage_m3","cumulative_external_volume_m3","mass_residual_m3"}){
                        if(std::fabs(fc.req(k).n - ec.req(k).n) > 1e-9) ok=false;
                    }
                }
            }
            if(ok){ std::cout<<"audit ok\n"; return 0; }
            std::cout<<"audit mismatch\n"; return 1;
        }
        throw std::runtime_error("unknown command");
    } catch(const std::exception& ex){
        std::cerr<<ex.what()<<"\n";
        return 1;
    }
}

} // namespace lockcore

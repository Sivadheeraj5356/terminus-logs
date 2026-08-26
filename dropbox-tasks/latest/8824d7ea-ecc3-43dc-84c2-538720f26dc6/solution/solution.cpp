#include <bits/stdc++.h>
#include <boost/multiprecision/cpp_int.hpp>
using namespace std;
using boost::multiprecision::cpp_int;
cpp_int absi(cpp_int x){return x<0?-x:x;}
cpp_int gcdii(cpp_int a, cpp_int b){a=absi(a);b=absi(b);while(b!=0){cpp_int r=a%b;a=b;b=r;}return a==0?1:a;}
struct Rat{cpp_int n,d;Rat(cpp_int a=0, cpp_int b=1){n=a;d=b;norm();}void norm(){if(d<0){n=-n;d=-d;}if(n==0){d=1;return;}cpp_int g=gcdii(n,d);n/=g;d/=g;}string str()const{return d==1?n.str():n.str()+"/"+d.str();}};
Rat operator+(const Rat&a,const Rat&b){return Rat(a.n*b.d+b.n*a.d,a.d*b.d);}Rat operator-(const Rat&a,const Rat&b){return Rat(a.n*b.d-b.n*a.d,a.d*b.d);}Rat operator-(const Rat&a){return Rat(-a.n,a.d);}Rat operator*(const Rat&a,const Rat&b){return Rat(a.n*b.n,a.d*b.d);}Rat operator/(const Rat&a,const Rat&b){return Rat(a.n*b.d,a.d*b.n);}bool operator==(const Rat&a,const Rat&b){return a.n==b.n&&a.d==b.d;}bool operator!=(const Rat&a,const Rat&b){return !(a==b);}bool operator<(const Rat&a,const Rat&b){return a.n*b.d<b.n*a.d;}bool operator>(const Rat&a,const Rat&b){return b<a;}bool operator<=(const Rat&a,const Rat&b){return !(b<a);}bool operator>=(const Rat&a,const Rat&b){return !(a<b);}struct Pt{Rat x,y;};
Pt operator+(const Pt&a,const Pt&b){return {a.x+b.x,a.y+b.y};}Pt operator-(const Pt&a,const Pt&b){return {a.x-b.x,a.y-b.y};}Pt operator*(const Pt&a,const Rat&t){return {a.x*t,a.y*t};}bool samep(const Pt&a,const Pt&b){return a.x==b.x&&a.y==b.y;}Rat crossp(const Pt&a,const Pt&b){return a.x*b.y-a.y*b.x;}Rat evalh(const Pt&p,const Rat&a,const Rat&b,const Rat&c){return a*p.x+b*p.y-c;}void clean(vector<Pt>&p){vector<Pt>q;for(auto &v:p){if(q.empty()||!samep(q.back(),v))q.push_back(v);}if(q.size()>1&&samep(q.front(),q.back()))q.pop_back();p=q;}
Pt interh(const Pt&p,const Pt&q,const Rat&a,const Rat&b,const Rat&c){Rat fp=evalh(p,a,b,c),fq=evalh(q,a,b,c);Rat t=fp/(fp-fq);return p+(q-p)*t;}
vector<Pt> cliph(vector<Pt> poly,Rat a,Rat b,Rat c){clean(poly);vector<Pt>out;if(poly.empty())return out;for(size_t i=0;i<poly.size();++i){Pt p=poly[i],q=poly[(i+1)%poly.size()];bool ip=evalh(p,a,b,c)<=Rat(0),iq=evalh(q,a,b,c)<=Rat(0);if(ip&&iq)out.push_back(q);else if(ip&&!iq)out.push_back(interh(p,q,a,b,c));else if(!ip&&iq){out.push_back(interh(p,q,a,b,c));out.push_back(q);}}clean(out);return out;}
Rat area2s(const vector<Pt>&p){Rat s(0);for(size_t i=0;i<p.size();++i)s=s+crossp(p[i],p[(i+1)%p.size()]);return s;}void ccw(vector<Pt>&p){if(area2s(p)<Rat(0))reverse(p.begin(),p.end());}
array<Rat,6> moments(vector<Pt> p){clean(p);if(p.size()<3)return {Rat(0),Rat(0),Rat(0),Rat(0),Rat(0),Rat(0)};Rat a2=area2s(p);if(a2<Rat(0)){reverse(p.begin(),p.end());a2=-a2;}Rat sx(0),sy(0),sx2(0),sxy(0),sy2(0);for(size_t i=0;i<p.size();++i){Pt u=p[i],v=p[(i+1)%p.size()];Rat cr=crossp(u,v);sx=sx+(u.x+v.x)*cr;sy=sy+(u.y+v.y)*cr;sx2=sx2+(u.x*u.x+u.x*v.x+v.x*v.x)*cr;sxy=sxy+(Rat(2)*u.x*u.y+u.x*v.y+v.x*u.y+Rat(2)*v.x*v.y)*cr;sy2=sy2+(u.y*u.y+u.y*v.y+v.y*v.y)*cr;}return {a2/Rat(2),sx/Rat(6),sy/Rat(6),sx2/Rat(12),sxy/Rat(24),sy2/Rat(12)};}
vector<Pt> convex_intersection(vector<Pt> subj,vector<Pt> clip){clean(subj);clean(clip);ccw(clip);vector<Pt>cur=subj;for(size_t i=0;i<clip.size();++i){Pt a=clip[i],b=clip[(i+1)%clip.size()];Rat dx=b.x-a.x,dy=b.y-a.y;Rat A=dy,B=-dx,C=dy*a.x-dx*a.y;cur=cliph(cur,A,B,C);}clean(cur);return cur;}

Pt reflectp(Pt p,Rat a,Rat b,Rat c){Rat s=a*p.x+b*p.y-c;Rat den=a*a+b*b;return {p.x-Rat(2)*a*s/den,p.y-Rat(2)*b*s/den};}
int solve_one(std::istream& in, std::ostream& out){int n;if(!(in>>n))return 0;vector<Pt> poly(n);for(int i=0;i<n;i++){long long x,y;in>>x>>y;poly[i]={Rat(x),Rat(y)};}long long ai,bi,ci;in>>ai>>bi>>ci;Rat a(ai),b(bi),c(ci);vector<Pt> stay=cliph(poly,a,b,c);vector<Pt> fold=cliph(poly,-a,-b,-c);for(auto &p:fold)p=reflectp(p,a,b,c);ccw(stay);ccw(fold);vector<Pt> both=convex_intersection(stay,fold);auto ms=moments(stay),mf=moments(fold),mb=moments(both);Rat visible=ms[0]+mf[0]-mb[0];Rat vx=ms[1]+mf[1]-mb[1];Rat vy=ms[2]+mf[2]-mb[2];out<<visible.str()<<" "<<mb[0].str()<<" "<<vx.str()<<" "<<vy.str()<<" "<<mb[1].str()<<" "<<mb[2].str()<<"\n";
    return 0;
}

int solve_second(std::istream& in, std::ostream& out){int n;if(!(in>>n))return 0;vector<Pt> poly(n);for(int i=0;i<n;i++){long long x,y;in>>x>>y;poly[i]={Rat(x),Rat(y)};}long long ai,bi,ci;in>>ai>>bi>>ci;Rat a(ai),b(bi),c(ci);vector<Pt> stay=cliph(poly,a,b,c);vector<Pt> fold=cliph(poly,-a,-b,-c);for(auto &p:fold)p=reflectp(p,a,b,c);ccw(stay);ccw(fold);vector<Pt> both=convex_intersection(stay,fold);auto ms=moments(stay),mf=moments(fold),mb=moments(both);array<Rat,6> vis;for(int i=0;i<6;i++)vis[i]=ms[i]+mf[i]-mb[i];out<<vis[0].str()<<" "<<mb[0].str()<<" "<<vis[1].str()<<" "<<vis[2].str()<<" "<<mb[1].str()<<" "<<mb[2].str()<<" "<<vis[3].str()<<" "<<vis[4].str()<<" "<<vis[5].str()<<" "<<mb[3].str()<<" "<<mb[4].str()<<" "<<mb[5].str()<<"\n";
    return 0;
}


static void feed_fnv_line(unsigned long long& hash, const std::string& line) {
    constexpr unsigned long long prime = 1099511628211ULL;
    for (unsigned char byte : line) {
        hash ^= static_cast<unsigned long long>(byte);
        hash *= prime;
    }
    hash ^= 10ULL;
    hash *= prime;
}

int solve_poly_trace(std::istream& in, std::ostream& out){
    int n;if(!(in>>n))return 0;
    vector<Pt> poly(n);
    for(int i=0;i<n;i++){long long x,y;in>>x>>y;poly[i]={Rat(x),Rat(y)};}
    long long ai,bi,ci;in>>ai>>bi>>ci;Rat a(ai),b(bi),c(ci);
    vector<Pt> stay=cliph(poly,a,b,c);
    vector<Pt> fold=cliph(poly,-a,-b,-c);
    for(auto &p:fold)p=reflectp(p,a,b,c);
    ccw(stay);ccw(fold);
    vector<Pt> both=convex_intersection(stay,fold);
    auto ms=moments(stay),mf=moments(fold),mb=moments(both);
    array<Rat,6> vis;for(int i=0;i<6;i++)vis[i]=ms[i]+mf[i]-mb[i];

    unsigned long long hash = 13679457532755275413ULL;
    auto emit = [&](const std::string& line) {
        out << line << '\n';
        feed_fnv_line(hash, line);
    };
    std::ostringstream head;
    head<<vis[0].str()<<" "<<mb[0].str()<<" "<<vis[1].str()<<" "<<vis[2].str()<<" "<<mb[1].str()<<" "<<mb[2].str()<<" "<<vis[3].str()<<" "<<vis[4].str()<<" "<<vis[5].str()<<" "<<mb[3].str()<<" "<<mb[4].str()<<" "<<mb[5].str();
    emit(head.str());
    auto emit_poly = [&](const std::string& label, const vector<Pt>& p) {
        for(size_t i=0;i<p.size();++i){
            const Pt& u=p[i];
            const Pt& v=p[(i+1)%p.size()];
            std::ostringstream line;
            line << label << ' ' << i << ' ' << u.x.str() << ' ' << u.y.str() << ' ' << crossp(u,v).str();
            emit(line.str());
        }
    };
    emit_poly("STAY", stay);
    emit_poly("FOLD", fold);
    emit_poly("DOUBLE", both);
    out << "POLY_AUDIT_178A9137 " << hash << '\n';
    return 0;
}


static std::string audit_canonicalize(const std::string& raw) {
    std::istringstream parts(raw);
    std::string token;
    std::string line;
    while (parts >> token) {
        if (!line.empty()) line.push_back(' ');
        line += token;
    }
    return line;
}

int main() {
    const std::string raw((std::istreambuf_iterator<char>(std::cin)),
                          std::istreambuf_iterator<char>());
    std::istringstream input(raw);
    std::string mode;
    if (!(input >> mode)) return 0;

    if (mode == "SECOND_178A9137") {
        return solve_second(input, std::cout);
    }

    if (mode == "POLY_TRACE_178A9137") {
        return solve_poly_trace(input, std::cout);
    }

    if (mode == "BATCH_SECOND_178A9137") {
        int total = 0;
        if (!(input >> total) || total < 2 || total > 16) return 2;
        unsigned long long hash = 7809847782465536327ULL;
        constexpr unsigned long long prime = 1099511628211ULL;
        for (int case_index = 0; case_index < total; ++case_index) {
            std::ostringstream captured;
            const int rc = solve_second(input, captured);
            if (rc != 0) return rc;
            const std::string line = audit_canonicalize(captured.str());
            if (line.empty()) return 3;
            std::cout << line << '\n';
            for (unsigned char byte : line) {
                hash ^= static_cast<unsigned long long>(byte);
                hash *= prime;
            }
            hash ^= 10ULL;
            hash *= prime;
        }
        std::cout << "SECOND_AUDIT_178A9137 " << hash << '\n';
        return 0;
    }

    if (mode != "BATCH_178A9137") {
        std::istringstream legacy(raw);
        return solve_one(legacy, std::cout);
    }

    int total = 0;
    if (!(input >> total) || total < 2 || total > 16) return 2;
    unsigned long long hash = 15886462886245262841ULL;
    constexpr unsigned long long prime = 1099511628211ULL;

    for (int case_index = 0; case_index < total; ++case_index) {
        std::ostringstream captured;
        const int rc = solve_one(input, captured);
        if (rc != 0) {
            return rc;
        }
        const std::string line = audit_canonicalize(captured.str());
        if (line.empty()) {
            return 3;
        }
        std::cout << line << '\n';
        for (unsigned char byte : line) {
            hash ^= static_cast<unsigned long long>(byte);
            hash *= prime;
        }
        hash ^= 10ULL;
        hash *= prime;
    }
    std::cout << "AUDIT_178A9137 " << hash << '\n';
    return 0;
}


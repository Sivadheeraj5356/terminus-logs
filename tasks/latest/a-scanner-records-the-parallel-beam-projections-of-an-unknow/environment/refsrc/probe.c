/* ct-probe: decode one projection-scan container and print, per record, the recovered
   scan as JSON (image_size, n_det, angles, sinogram). Reads one base64 line on stdin.
   Hand-rolled SHA-256 so the binary leaks no crypto library symbol. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ---- SHA-256 ---- */
typedef struct { uint32_t s[8]; uint64_t len; uint8_t buf[64]; size_t n; } sha;
static uint32_t ror(uint32_t x, int r){ return (x>>r)|(x<<(32-r)); }
static const uint32_t K[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
static void sha_init(sha *c){ uint32_t iv[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}; memcpy(c->s,iv,32); c->len=0; c->n=0; }
static void sha_block(sha *c, const uint8_t *p){
  uint32_t w[64], a,b,cc,d,e,f,g,h,t1,t2; int i;
  for(i=0;i<16;i++) w[i]=(p[i*4]<<24)|(p[i*4+1]<<16)|(p[i*4+2]<<8)|p[i*4+3];
  for(i=16;i<64;i++){ uint32_t s0=ror(w[i-15],7)^ror(w[i-15],18)^(w[i-15]>>3);
    uint32_t s1=ror(w[i-2],17)^ror(w[i-2],19)^(w[i-2]>>10); w[i]=w[i-16]+s0+w[i-7]+s1; }
  a=c->s[0];b=c->s[1];cc=c->s[2];d=c->s[3];e=c->s[4];f=c->s[5];g=c->s[6];h=c->s[7];
  for(i=0;i<64;i++){ uint32_t S1=ror(e,6)^ror(e,11)^ror(e,25); uint32_t ch=(e&f)^((~e)&g);
    t1=h+S1+ch+K[i]+w[i]; uint32_t S0=ror(a,2)^ror(a,13)^ror(a,22); uint32_t maj=(a&b)^(a&cc)^(b&cc);
    t2=S0+maj; h=g;g=f;f=e;e=d+t1;d=cc;cc=b;b=a;a=t1+t2; }
  c->s[0]+=a;c->s[1]+=b;c->s[2]+=cc;c->s[3]+=d;c->s[4]+=e;c->s[5]+=f;c->s[6]+=g;c->s[7]+=h;
}
static void sha_update(sha *c, const uint8_t *p, size_t n){
  c->len+=n;
  while(n){ size_t k=64-c->n; if(k>n)k=n; memcpy(c->buf+c->n,p,k); c->n+=k; p+=k; n-=k;
    if(c->n==64){ sha_block(c,c->buf); c->n=0; } }
}
static void sha_final(sha *c, uint8_t *out){
  uint64_t bits=c->len*8; uint8_t pad=0x80; sha_update(c,&pad,1);
  uint8_t z=0; while(c->n!=56) sha_update(c,&z,1);
  uint8_t L[8]; for(int i=0;i<8;i++) L[i]=(bits>>(56-i*8))&0xFF; sha_update(c,L,8);
  for(int i=0;i<8;i++){ out[i*4]=(c->s[i]>>24)&0xFF; out[i*4+1]=(c->s[i]>>16)&0xFF; out[i*4+2]=(c->s[i]>>8)&0xFF; out[i*4+3]=c->s[i]&0xFF; }
}
static void sha256(const uint8_t *p, size_t n, uint8_t *out){ sha c; sha_init(&c); sha_update(&c,p,n); sha_final(&c,out); }

static void keystream(const uint8_t *state, uint8_t dom, size_t n, uint8_t *out){
  uint32_t ctr=0; size_t o=0;
  while(o<n){
    uint8_t in[37]; memcpy(in,state,32); in[32]=dom;
    in[33]=(ctr>>24)&0xFF; in[34]=(ctr>>16)&0xFF; in[35]=(ctr>>8)&0xFF; in[36]=ctr&0xFF;
    uint8_t blk[32]; sha256(in,37,blk);
    size_t k=32; if(k>n-o)k=n-o; memcpy(out+o,blk,k); o+=k; ctr++;
  }
}
static void fy(const uint8_t *seed4, int n, int *p){
  uint32_t s=((uint32_t)seed4[0]<<24)|((uint32_t)seed4[1]<<16)|((uint32_t)seed4[2]<<8)|seed4[3];
  for(int i=0;i<n;i++) p[i]=i;
  for(int i=n-1;i>0;i--){ s=s*1664525u+1013904223u; int j=s%(i+1); int t=p[i];p[i]=p[j];p[j]=t; }
}
static uint64_t read_uvarint(const uint8_t *buf, size_t *pos){
  uint64_t result=0; int shift=0;
  for(;;){ uint8_t b=buf[(*pos)++]; result |= (uint64_t)(b&0x7F)<<shift; if(!(b&0x80)) return result; shift+=7; }
}
static int b64val(int c){ if(c>='A'&&c<='Z')return c-'A'; if(c>='a'&&c<='z')return c-'a'+26;
  if(c>='0'&&c<='9')return c-'0'+52; if(c=='+')return 62; if(c=='/')return 63; return -1; }
static size_t b64dec(const char *in, uint8_t *out){
  size_t o=0; int q[4],qn=0;
  for(const char *p=in;*p;p++){ if(*p=='='||*p=='\n'||*p=='\r'||*p==' ')continue;
    int v=b64val((unsigned char)*p); if(v<0)continue; q[qn++]=v;
    if(qn==4){ out[o++]=(q[0]<<2)|(q[1]>>4); out[o++]=((q[1]&15)<<4)|(q[2]>>2); out[o++]=((q[2]&3)<<6)|q[3]; qn=0; } }
  if(qn==2){ out[o++]=(q[0]<<2)|(q[1]>>4); }
  else if(qn==3){ out[o++]=(q[0]<<2)|(q[1]>>4); out[o++]=((q[1]&15)<<4)|(q[2]>>2); }
  return o;
}

#define QMAX 4095.0
#define RMAX 100.0
#define ASCALE 1000000.0
static double mu_of(const uint8_t *state){
  uint8_t in[33]; memcpy(in,state,32); in[32]=0x04; uint8_t d[32]; sha256(in,33,d);
  return (double)(4 + (int)d[0]%37);
}
static double expand(int q, double m){
  double u = expm1((double)q/QMAX*log1p(m))/m; return u*RMAX;
}

int main(void){
  static char line[1<<20]; if(!fgets(line,sizeof line,stdin)){ return 1; }
  static uint8_t blob[1<<19]; size_t bl=b64dec(line,blob);
  if(bl<8 || blob[0]!=0x54 || blob[1]!=0x43){ fprintf(stderr,"bad sync\n"); return 2; }
  int nrec=(blob[2]<<8)|blob[3];
  uint8_t sin[16]; sin[0]=0x54; sin[1]=0x43; memcpy(sin+2,blob+4,4);
  memcpy(sin+6,"CTSCAN-1",8);
  uint8_t state[32]; sha256(sin,14,state);
  size_t pos=8;
  printf("[");
  for(int r=0;r<nrec;r++){
    double m=mu_of(state);
    uint64_t clen=read_uvarint(blob,&pos);
    int n=(int)clen;
    if((size_t)(pos+n)>bl || n>65536){ fprintf(stderr,"short\n"); return 3; }
    static uint8_t cipher[65536]; memcpy(cipher,blob+pos,n); pos+=n;
    uint8_t k2in[33]; memcpy(k2in,state,32); k2in[32]=0x06; uint8_t k2d[32]; sha256(k2in,33,k2d);
    static int sb2[256]; fy(k2d,256,sb2);
    uint8_t v2in[33]; memcpy(v2in,state,32); v2in[32]=0x07; uint8_t v2d[32]; sha256(v2in,33,v2d);
    static uint8_t ks2[65536]; keystream(state,0x05,n,ks2);
    static uint8_t sboxed[65536];
    { int prev=v2d[0]; for(int j=0;j<n;j++){ sboxed[j]=(uint8_t)(cipher[j]^ks2[j]^sb2[prev]); prev=cipher[j]; } }
    uint8_t sdin[33]; memcpy(sdin,state,32); sdin[32]=0x03; uint8_t sd[32]; sha256(sdin,33,sd);
    static int sbox[256]; fy(sd,256,sbox); int inv[256]; for(int k=0;k<256;k++) inv[sbox[k]]=k;
    static uint8_t permuted[65536]; for(int j=0;j<n;j++) permuted[j]=(uint8_t)inv[sboxed[j]];
    uint8_t pdin[33]; memcpy(pdin,state,32); pdin[32]=0x01; uint8_t pd[32]; sha256(pdin,33,pd);
    static int perm[65536]; fy(pd,n,perm);
    static uint8_t masked[65536]; for(int j=0;j<n;j++) masked[j]=permuted[perm[j]];
    static uint8_t ks[65536]; keystream(state,0x00,n,ks);
    static uint8_t plain[65536]; for(int j=0;j<n;j++) plain[j]=masked[j]^ks[j];
    /* parse the recovered plaintext into the scan */
    size_t p2=0;
    uint64_t isz=read_uvarint(plain,&p2);
    uint64_t ndet=read_uvarint(plain,&p2);
    uint64_t na=read_uvarint(plain,&p2);
    printf("%s{\"image_size\":%llu,\"n_det\":%llu,\"angles\":[",
           r?",":"", (unsigned long long)isz, (unsigned long long)ndet);
    static uint64_t araw[4096];
    for(uint64_t i=0;i<na;i++){ araw[i]=read_uvarint(plain,&p2); }
    for(uint64_t i=0;i<na;i++){ printf("%s%.6f", i?",":"", (double)araw[i]/ASCALE); }
    printf("],\"sinogram\":[");
    for(uint64_t i=0;i<na;i++){
      printf("%s[", i?",":"");
      for(uint64_t j=0;j<ndet;j++){
        int q=((int)plain[p2]<<8)|(int)plain[p2+1]; p2+=2;
        printf("%s%.6f", j?",":"", expand(q,m));
      }
      printf("]");
    }
    printf("]}");
    static uint8_t cin[65536+32]; memcpy(cin,state,32); memcpy(cin+32,plain,n); sha256(cin,32+n,state);
  }
  printf("]\n");
  return 0;
}

#!/bin/bash
# Reference implementation of the amr_mhd solver: a 2D ideal-MHD, finite-volume Godunov
# (MUSCL-MC + HLL) scheme with Balsara-Spicer constrained transport and SSP-RK2 on a
# two-level, non-subcycling block-adaptive mesh. The complete source is written into the
# project, built with the toolchain already present, then exercised on the bespoke invariants
# (second-order convergence, machine-zero divergence including across coarse-fine boundaries,
# conservation via refluxing, positivity, and bit-exact restart).
set -euo pipefail

cd /app
mkdir -p /app/src

cat > /app/src/amr_mhd.cpp <<'AMR_MHD_EOF'
// amr_mhd: 2D ideal MHD, finite-volume Godunov (MUSCL-MC + HLL) with Balsara-Spicer
// constrained transport, SSP-RK2, on a two-level block-adaptive Cartesian mesh (ratio 2,
// non-subcycling). Reference implementation.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <utility>
#include <fstream>
#include <sstream>
#include <algorithm>
using namespace std;
static const int RHO=0,MX=1,MY=2,MZ=3,ENE=4,BX=5,BY=6,BZ=7,NV=8;
static double GAM=5.0/3.0;
static const int GH=2;
enum{PER=0,OUTF=1};

struct Grid{
  int nx,ny; double dx,dy,Lx,Ly; int NX,NY;
  vector<double> U,bx,by;
  int cidx(int i,int j,int v)const{return (j*NX+i)*NV+v;}
  int bxi(int i,int j)const{return j*(NX+1)+i;}
  int byi(int i,int j)const{return j*NX+i;}
  double Bxc(int i,int j)const{return 0.5*(bx[bxi(i,j)]+bx[bxi(i+1,j)]);}
  double Byc(int i,int j)const{return 0.5*(by[byi(i,j)]+by[byi(i,j+1)]);}
};
static void alloc(Grid&g,int nx,int ny,double Lx,double Ly){
  g.nx=nx;g.ny=ny;g.Lx=Lx;g.Ly=Ly;g.dx=Lx/nx;g.dy=Ly/ny;g.NX=nx+2*GH;g.NY=ny+2*GH;
  g.U.assign((size_t)g.NX*g.NY*NV,0.0);
  g.bx.assign((size_t)(g.NX+1)*g.NY,0.0);
  g.by.assign((size_t)g.NX*(g.NY+1),0.0);
}
static inline void cons2prim(const double*U,double*W){
  double rho=U[RHO];W[RHO]=rho;double u=U[MX]/rho,v=U[MY]/rho,w=U[MZ]/rho;
  W[MX]=u;W[MY]=v;W[MZ]=w;double Bx=U[BX],By=U[BY],Bz=U[BZ];
  double ke=0.5*rho*(u*u+v*v+w*w),me=0.5*(Bx*Bx+By*By+Bz*Bz);
  W[ENE]=(GAM-1.0)*(U[ENE]-ke-me);W[BX]=Bx;W[BY]=By;W[BZ]=Bz;
}
static inline void prim2cons(const double*W,double*U){
  double rho=W[RHO],u=W[MX],v=W[MY],w=W[MZ],p=W[ENE],Bx=W[BX],By=W[BY],Bz=W[BZ];
  U[RHO]=rho;U[MX]=rho*u;U[MY]=rho*v;U[MZ]=rho*w;
  U[ENE]=p/(GAM-1.0)+0.5*rho*(u*u+v*v+w*w)+0.5*(Bx*Bx+By*By+Bz*Bz);
  U[BX]=Bx;U[BY]=By;U[BZ]=Bz;
}
static inline void flux(const double*W,int d,double*F){
  double rho=W[RHO],u=W[MX],v=W[MY],w=W[MZ],p=W[ENE],Bx=W[BX],By=W[BY],Bz=W[BZ];
  double B2=Bx*Bx+By*By+Bz*Bz,ptot=p+0.5*B2,ke=0.5*rho*(u*u+v*v+w*w);
  double E=p/(GAM-1.0)+ke+0.5*B2,vB=u*Bx+v*By+w*Bz;
  if(d==0){double un=u;
    F[RHO]=rho*un;F[MX]=rho*un*u+ptot-Bx*Bx;F[MY]=rho*un*v-Bx*By;F[MZ]=rho*un*w-Bx*Bz;
    F[ENE]=(E+ptot)*un-Bx*vB;F[BX]=0;F[BY]=u*By-v*Bx;F[BZ]=u*Bz-w*Bx;
  }else{double un=v;
    F[RHO]=rho*un;F[MX]=rho*un*u-By*Bx;F[MY]=rho*un*v+ptot-By*By;F[MZ]=rho*un*w-By*Bz;
    F[ENE]=(E+ptot)*un-By*vB;F[BX]=v*Bx-u*By;F[BY]=0;F[BZ]=v*Bz-w*By;}
}
static inline double cfast(const double*W,int d){
  double rho=W[RHO],p=W[ENE],Bx=W[BX],By=W[BY],Bz=W[BZ];
  double a2=GAM*p/rho,b2=(Bx*Bx+By*By+Bz*Bz)/rho,bn2=(d==0?Bx*Bx:By*By)/rho;
  double t=a2+b2,disc=t*t-4*a2*bn2;if(disc<0)disc=0;return sqrt(0.5*(t+sqrt(disc)));
}
static inline double mclim(double dm,double dp){
  if(dm*dp<=0)return 0.0;double s=(dm>0?1.0:-1.0);
  return s*min(min(2*fabs(dm),2*fabs(dp)),0.5*fabs(dm+dp));
}
static inline void hll(const double*WL,const double*WR,int d,double*F){
  double UL[NV],UR[NV],FL[NV],FR[NV];prim2cons(WL,UL);prim2cons(WR,UR);flux(WL,d,FL);flux(WR,d,FR);
  double unL=WL[MX+d],unR=WR[MX+d],cL=cfast(WL,d),cR=cfast(WR,d);
  double SL=min(unL-cL,unR-cR),SR=max(unL+cL,unR+cR);
  if(SL>=0){for(int v=0;v<NV;v++)F[v]=FL[v];return;}
  if(SR<=0){for(int v=0;v<NV;v++)F[v]=FR[v];return;}
  double inv=1.0/(SR-SL);for(int v=0;v<NV;v++)F[v]=(SR*FL[v]-SL*FR[v]+SL*SR*(UR[v]-UL[v]))*inv;
}
static double PFLOOR=1e-9,RHOFLOOR=1e-9;static long protectCount=0;
static long blocksCreated=0,blocksDeleted=0,nblocksMax=0,nblocksMin=-1;

// ---- ghost fills (bc-aware) ----
static void fillCellGhost(Grid&g,int bc){
  int nx=g.nx,ny=g.ny;
  for(int j=GH;j<GH+ny;j++)for(int i=GH;i<GH+nx;i++){g.U[g.cidx(i,j,BX)]=g.Bxc(i,j);g.U[g.cidx(i,j,BY)]=g.Byc(i,j);}
  for(int j=0;j<g.NY;j++)for(int i=0;i<g.NX;i++){int si=i,sj=j;
    if(bc==PER){if(i<GH)si=i+nx;else if(i>=GH+nx)si=i-nx; if(j<GH)sj=j+ny;else if(j>=GH+ny)sj=j-ny;}
    else{si=min(max(i,GH),GH+nx-1);sj=min(max(j,GH),GH+ny-1);}
    if(si==i&&sj==j)continue; for(int v=0;v<NV;v++)g.U[g.cidx(i,j,v)]=g.U[g.cidx(si,sj,v)];}
}
static void fillFaceGhost(Grid&g,int bc){
  int nx=g.nx,ny=g.ny;
  for(int j=0;j<g.NY;j++)for(int i=0;i<=g.NX;i++){int si=i,sj=j;
    if(bc==PER){if(i<GH)si=i+nx;else if(i>GH+nx)si=i-nx; if(i==GH+nx)si=GH; if(j<GH)sj=j+ny;else if(j>=GH+ny)sj=j-ny;}
    else{si=min(max(i,GH),GH+nx);sj=min(max(j,GH),GH+ny-1);}
    if(si==i&&sj==j)continue; g.bx[g.bxi(i,j)]=g.bx[g.bxi(si,sj)];}
  for(int j=0;j<=g.NY;j++)for(int i=0;i<g.NX;i++){int si=i,sj=j;
    if(bc==PER){if(i<GH)si=i+nx;else if(i>=GH+nx)si=i-nx; if(j<GH)sj=j+ny;else if(j>GH+ny)sj=j-ny; if(j==GH+ny)sj=GH;}
    else{si=min(max(i,GH),GH+nx-1);sj=min(max(j,GH),GH+ny);}
    if(si==i&&sj==j)continue; g.by[g.byi(i,j)]=g.by[g.byi(si,sj)];}
}

struct AMR{
  Grid c,f; int BF; int bc;
  vector<char> valid,covered;
  set<pair<int,int>> blocks; int nbx,nby;
  bool valC(int fi,int fj)const{return valid[fj*f.NX+fi]!=0;}
  bool cov(int I,int J)const{ // coarse covered, bc-aware for out-of-interior
    if(I>=GH&&I<GH+c.nx&&J>=GH&&J<GH+c.ny)return covered[J*c.NX+I]!=0;
    if(bc==PER){int i=I,j=J;if(i<GH)i+=c.nx;else if(i>=GH+c.nx)i-=c.nx;if(j<GH)j+=c.ny;else if(j>=GH+c.ny)j-=c.ny;return covered[j*c.NX+i]!=0;}
    return false;}
};
static void rebuildMasks(AMR&a){
  a.valid.assign((size_t)a.f.NX*a.f.NY,0);a.covered.assign((size_t)a.c.NX*a.c.NY,0);
  for(auto&b:a.blocks){int bi=b.first,bj=b.second;
    for(int t=0;t<a.BF;t++)for(int s=0;s<a.BF;s++){int fi=GH+bi*a.BF+s,fj=GH+bj*a.BF+t;a.valid[fj*a.f.NX+fi]=1;}}
  for(int J=GH;J<GH+a.c.ny;J++)for(int I=GH;I<GH+a.c.nx;I++){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);
    bool cvd=a.valid[FJ*a.f.NX+FI]&&a.valid[FJ*a.f.NX+FI+1]&&a.valid[(FJ+1)*a.f.NX+FI]&&a.valid[(FJ+1)*a.f.NX+FI+1];
    a.covered[J*a.c.NX+I]=cvd?1:0;}
}
static inline int parentIdx(int fi){int r=fi-GH;int q=(r>=0)?r/2:-(((-r)+1)/2);return GH+q;}
static void fillFine(AMR&a){
  Grid&f=a.f,&c=a.c;
  for(int fj=GH;fj<GH+f.ny;fj++)for(int fi=GH;fi<GH+f.nx;fi++)if(a.valC(fi,fj)){
    f.U[f.cidx(fi,fj,BX)]=f.Bxc(fi,fj);f.U[f.cidx(fi,fj,BY)]=f.Byc(fi,fj);}
  static vector<double> csx,csy;csx.assign((size_t)c.NX*c.NY*NV,0.0);csy.assign((size_t)c.NX*c.NY*NV,0.0);
  for(int J=1;J<c.NY-1;J++)for(int I=1;I<c.NX-1;I++)for(int v=0;v<NV;v++){double cc=c.U[c.cidx(I,J,v)];
    csx[(J*c.NX+I)*NV+v]=mclim(cc-c.U[c.cidx(I-1,J,v)],c.U[c.cidx(I+1,J,v)]-cc);
    csy[(J*c.NX+I)*NV+v]=mclim(cc-c.U[c.cidx(I,J-1,v)],c.U[c.cidx(I,J+1,v)]-cc);}
  for(int fj=0;fj<f.NY;fj++)for(int fi=0;fi<f.NX;fi++){
    if(fi>=GH&&fi<GH+f.nx&&fj>=GH&&fj<GH+f.ny&&a.valC(fi,fj))continue;
    int I=parentIdx(fi),J=parentIdx(fj);if(I<0)I=0;if(I>=c.NX)I=c.NX-1;if(J<0)J=0;if(J>=c.NY)J=c.NY-1;
    int s=(fi-GH)-2*(I-GH),t=(fj-GH)-2*(J-GH);double fx=(s-0.5)/2.0,fy=(t-0.5)/2.0;
    for(int v=0;v<NV;v++)f.U[f.cidx(fi,fj,v)]=c.U[c.cidx(I,J,v)]+fx*csx[(J*c.NX+I)*NV+v]+fy*csy[(J*c.NX+I)*NV+v];}
  if(a.bc==PER){int nx=f.nx,ny=f.ny;
    for(int fj=0;fj<f.NY;fj++)for(int fi=0;fi<f.NX;fi++){int si=fi,sj=fj;
      if(fi<GH)si=fi+nx;else if(fi>=GH+nx)si=fi-nx; if(fj<GH)sj=fj+ny;else if(fj>=GH+ny)sj=fj-ny;
      if(si==fi&&sj==fj)continue; if(si>=GH&&si<GH+nx&&sj>=GH&&sj<GH+ny&&a.valC(si,sj))
        for(int v=0;v<NV;v++)f.U[f.cidx(fi,fj,v)]=f.U[f.cidx(si,sj,v)];}}
}
struct Fluxes{vector<double> Fx,Fy,Ez;};
static void buildFluxes(const Grid&g,Fluxes&fx){
  int NX=g.NX,NY=g.NY;
  fx.Fx.assign((size_t)(NX+1)*NY*NV,0.0);fx.Fy.assign((size_t)NX*(NY+1)*NV,0.0);fx.Ez.assign((size_t)(NX+1)*(NY+1),0.0);
  static vector<double> W,sx,sy;W.assign((size_t)NX*NY*NV,0.0);sx.assign(W.size(),0.0);sy.assign(W.size(),0.0);
  for(int j=0;j<NY;j++)for(int i=0;i<NX;i++)cons2prim(&g.U[g.cidx(i,j,0)],&W[(j*NX+i)*NV]);
  for(int j=1;j<NY-1;j++)for(int i=1;i<NX-1;i++)for(int v=0;v<NV;v++){double cc=W[(j*NX+i)*NV+v];
    sx[(j*NX+i)*NV+v]=mclim(cc-W[(j*NX+i-1)*NV+v],W[(j*NX+i+1)*NV+v]-cc);
    sy[(j*NX+i)*NV+v]=mclim(cc-W[((j-1)*NX+i)*NV+v],W[((j+1)*NX+i)*NV+v]-cc);}
  for(int j=1;j<NY-1;j++)for(int i=1;i<=NX-1;i++){double WLr[NV],WRr[NV];
    for(int v=0;v<NV;v++){WLr[v]=W[(j*NX+i-1)*NV+v]+0.5*sx[(j*NX+i-1)*NV+v];WRr[v]=W[(j*NX+i)*NV+v]-0.5*sx[(j*NX+i)*NV+v];}
    WLr[BX]=g.bx[g.bxi(i,j)];WRr[BX]=g.bx[g.bxi(i,j)];double F[NV];hll(WLr,WRr,0,F);
    for(int v=0;v<NV;v++)fx.Fx[((size_t)j*(NX+1)+i)*NV+v]=F[v];}
  for(int j=1;j<=NY-1;j++)for(int i=1;i<NX-1;i++){double WLr[NV],WRr[NV];
    for(int v=0;v<NV;v++){WLr[v]=W[((j-1)*NX+i)*NV+v]+0.5*sy[((j-1)*NX+i)*NV+v];WRr[v]=W[(j*NX+i)*NV+v]-0.5*sy[(j*NX+i)*NV+v];}
    WLr[BY]=g.by[g.byi(i,j)];WRr[BY]=g.by[g.byi(i,j)];double F[NV];hll(WLr,WRr,1,F);
    for(int v=0;v<NV;v++)fx.Fy[((size_t)j*NX+i)*NV+v]=F[v];}
  for(int j=1;j<=NY-1;j++)for(int i=1;i<=NX-1;i++){
    double exf_b=-fx.Fx[((size_t)(j-1)*(NX+1)+i)*NV+BY],exf_t=-fx.Fx[((size_t)j*(NX+1)+i)*NV+BY];
    double eyf_l=fx.Fy[((size_t)j*NX+(i-1))*NV+BX],eyf_r=fx.Fy[((size_t)j*NX+i)*NV+BX];
    fx.Ez[(size_t)j*(NX+1)+i]=0.25*(exf_b+exf_t+eyf_l+eyf_r);}
}
static void computeRHS2(AMR&a,vector<double>&dUc,vector<double>&dbxc,vector<double>&dbyc,
                        vector<double>&dUf,vector<double>&dbxf,vector<double>&dbyf){
  Grid&c=a.c,&f=a.f;
  fillCellGhost(c,a.bc);fillFaceGhost(c,a.bc);fillFine(a);
  Fluxes Fc,Ff;buildFluxes(c,Fc);buildFluxes(f,Ff);
  int cNX=c.NX,fNX=f.NX;
  if(a.bc==PER){
    for(int j=0;j<f.NY;j++)for(int v=0;v<NV;v++)Ff.Fx[((size_t)j*(fNX+1)+(GH+f.nx))*NV+v]=Ff.Fx[((size_t)j*(fNX+1)+GH)*NV+v];
    for(int i=0;i<f.NX;i++)for(int v=0;v<NV;v++)Ff.Fy[((size_t)(GH+f.ny)*fNX+i)*NV+v]=Ff.Fy[((size_t)GH*fNX+i)*NV+v];
    for(int j=0;j<=f.NY;j++)Ff.Ez[(size_t)j*(fNX+1)+(GH+f.nx)]=Ff.Ez[(size_t)j*(fNX+1)+GH];
    for(int i=0;i<=f.NX;i++)Ff.Ez[(size_t)(GH+f.ny)*(fNX+1)+i]=Ff.Ez[(size_t)GH*(fNX+1)+i];
  }
  // EMF sync
  for(int J=GH;J<=GH+c.ny;J++)for(int I=GH;I<=GH+c.nx;I++){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);
    int wFI=FI,wFJ=FJ;if(a.bc==PER){if(wFI>=GH+f.nx)wFI-=f.nx;if(wFJ>=GH+f.ny)wFJ-=f.ny;}
    if(wFI<0||wFI>f.NX||wFJ<0||wFJ>f.NY)continue; bool any=false;
    for(int dj=-1;dj<=0;dj++)for(int di=-1;di<=0;di++){int ci=wFI+di,cj=wFJ+dj;
      if(ci>=GH&&ci<GH+f.nx&&cj>=GH&&cj<GH+f.ny&&a.valC(ci,cj))any=true;}
    if(any)Fc.Ez[(size_t)J*(cNX+1)+I]=Ff.Ez[(size_t)wFJ*(fNX+1)+wFI];}
  // flux reflux
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<=GH+c.nx;I++){bool covL=a.cov(I-1,J),covR=a.cov(I,J);
    if(covL!=covR){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);int wFI=FI;if(a.bc==PER&&wFI>=GH+f.nx)wFI-=f.nx;
      if(wFI<0||wFI>f.NX)continue;
      for(int v=0;v<NV;v++)Fc.Fx[((size_t)J*(cNX+1)+I)*NV+v]=0.5*(Ff.Fx[((size_t)FJ*(fNX+1)+wFI)*NV+v]+Ff.Fx[((size_t)(FJ+1)*(fNX+1)+wFI)*NV+v]);}}
  for(int J=GH;J<=GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++){bool covB=a.cov(I,J-1),covT=a.cov(I,J);
    if(covB!=covT){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);int wFJ=FJ;if(a.bc==PER&&wFJ>=GH+f.ny)wFJ-=f.ny;
      if(wFJ<0||wFJ>f.NY)continue;
      for(int v=0;v<NV;v++)Fc.Fy[((size_t)J*cNX+I)*NV+v]=0.5*(Ff.Fy[((size_t)wFJ*fNX+FI)*NV+v]+Ff.Fy[((size_t)wFJ*fNX+FI+1)*NV+v]);}}
  dUc.assign((size_t)c.NX*c.NY*NV,0.0);dbxc.assign((size_t)(c.NX+1)*c.NY,0.0);dbyc.assign((size_t)c.NX*(c.NY+1),0.0);
  int comps[6]={RHO,MX,MY,MZ,ENE,BZ};
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++)for(int cc=0;cc<6;cc++){int v=comps[cc];
    double fl=Fc.Fx[((size_t)J*(cNX+1)+I)*NV+v],fr=Fc.Fx[((size_t)J*(cNX+1)+(I+1))*NV+v];
    double fb=Fc.Fy[((size_t)J*cNX+I)*NV+v],ft=Fc.Fy[((size_t)(J+1)*cNX+I)*NV+v];
    dUc[c.cidx(I,J,v)]=-(fr-fl)/c.dx-(ft-fb)/c.dy;}
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<=GH+c.nx;I++){double e0=Fc.Ez[(size_t)J*(cNX+1)+I],e1=Fc.Ez[(size_t)(J+1)*(cNX+1)+I];dbxc[c.bxi(I,J)]=-(e1-e0)/c.dy;}
  for(int J=GH;J<=GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++){double e0=Fc.Ez[(size_t)J*(cNX+1)+I],e1=Fc.Ez[(size_t)J*(cNX+1)+(I+1)];dbyc[c.byi(I,J)]=(e1-e0)/c.dx;}
  dUf.assign((size_t)f.NX*f.NY*NV,0.0);dbxf.assign((size_t)(f.NX+1)*f.NY,0.0);dbyf.assign((size_t)f.NX*(f.NY+1),0.0);
  for(int J=GH;J<GH+f.ny;J++)for(int I=GH;I<GH+f.nx;I++)if(a.valC(I,J))for(int cc=0;cc<6;cc++){int v=comps[cc];
    double fl=Ff.Fx[((size_t)J*(fNX+1)+I)*NV+v],fr=Ff.Fx[((size_t)J*(fNX+1)+(I+1))*NV+v];
    double fb=Ff.Fy[((size_t)J*fNX+I)*NV+v],ft=Ff.Fy[((size_t)(J+1)*fNX+I)*NV+v];
    dUf[f.cidx(I,J,v)]=-(fr-fl)/f.dx-(ft-fb)/f.dy;}
  for(int J=GH;J<GH+f.ny;J++)for(int I=GH;I<=GH+f.nx;I++){bool va=(I-1>=GH&&a.valC(I-1,J)),vb=(I<GH+f.nx&&a.valC(I,J));if(!(va||vb))continue;
    double e0=Ff.Ez[(size_t)J*(fNX+1)+I],e1=Ff.Ez[(size_t)(J+1)*(fNX+1)+I];dbxf[f.bxi(I,J)]=-(e1-e0)/f.dy;}
  for(int J=GH;J<=GH+f.ny;J++)for(int I=GH;I<GH+f.nx;I++){bool va=(J-1>=GH&&a.valC(I,J-1)),vb=(J<GH+f.ny&&a.valC(I,J));if(!(va||vb))continue;
    double e0=Ff.Ez[(size_t)J*(fNX+1)+I],e1=Ff.Ez[(size_t)J*(fNX+1)+(I+1)];dbyf[f.byi(I,J)]=(e1-e0)/f.dx;}
}
static void restrictFineToCoarse(AMR&a){
  Grid&c=a.c,&f=a.f;int comps[6]={RHO,MX,MY,MZ,ENE,BZ};
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++)if(a.covered[J*c.NX+I]){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);
    for(int cc=0;cc<6;cc++){int v=comps[cc];
      c.U[c.cidx(I,J,v)]=0.25*(f.U[f.cidx(FI,FJ,v)]+f.U[f.cidx(FI+1,FJ,v)]+f.U[f.cidx(FI,FJ+1,v)]+f.U[f.cidx(FI+1,FJ+1,v)]);}}
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<=GH+c.nx;I++){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);int wFI=FI;if(a.bc==PER&&wFI>=GH+f.nx)wFI-=f.nx;if(wFI<0||wFI>f.NX)continue;
    auto xact=[&](int fi,int fj){bool va=(fi-1>=GH&&a.valC(fi-1,fj)),vb=(fi<GH+f.nx&&a.valC(fi,fj));return va||vb;};
    if(xact(wFI,FJ)&&xact(wFI,FJ+1))c.bx[c.bxi(I,J)]=0.5*(f.bx[f.bxi(wFI,FJ)]+f.bx[f.bxi(wFI,FJ+1)]);}
  for(int J=GH;J<=GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++){int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);int wFJ=FJ;if(a.bc==PER&&wFJ>=GH+f.ny)wFJ-=f.ny;if(wFJ<0||wFJ>f.NY)continue;
    auto yact=[&](int fi,int fj){bool va=(fj-1>=GH&&a.valC(fi,fj-1)),vb=(fj<GH+f.ny&&a.valC(fi,fj));return va||vb;};
    if(yact(FI,wFJ)&&yact(FI+1,wFJ))c.by[c.byi(I,J)]=0.5*(f.by[f.byi(FI,wFJ)]+f.by[f.byi(FI+1,wFJ)]);}
}
static void applyFloorGrid(Grid&g,const vector<char>*mask){
  for(int j=GH;j<GH+g.ny;j++)for(int i=GH;i<GH+g.nx;i++){if(mask&&!(*mask)[j*g.NX+i])continue;
    double*U=&g.U[g.cidx(i,j,0)];bool prot=false;if(U[RHO]<RHOFLOOR){U[RHO]=RHOFLOOR;prot=true;}
    double W[NV];cons2prim(U,W);if(W[ENE]<PFLOOR){W[ENE]=PFLOOR;prim2cons(W,U);prot=true;}if(prot)protectCount++;}
}
static double dtCFL2(AMR&a,double cfl){double mn=1e30;Grid&c=a.c,&f=a.f;
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++)if(!a.covered[J*c.NX+I]){double W[NV];cons2prim(&c.U[c.cidx(I,J,0)],W);
    double cx=cfast(W,0),cy=cfast(W,1);mn=min(mn,c.dx/(fabs(W[MX])+cx));mn=min(mn,c.dy/(fabs(W[MY])+cy));}
  for(int J=GH;J<GH+f.ny;J++)for(int I=GH;I<GH+f.nx;I++)if(a.valC(I,J)){double W[NV];cons2prim(&f.U[f.cidx(I,J,0)],W);
    double cx=cfast(W,0),cy=cfast(W,1);mn=min(mn,f.dx/(fabs(W[MX])+cx));mn=min(mn,f.dy/(fabs(W[MY])+cy));}
  return cfl*mn;}
static void step2(AMR&a,double dt){
  Grid c0=a.c,f0=a.f;vector<double> dUc,dbxc,dbyc,dUf,dbxf,dbyf;
  computeRHS2(a,dUc,dbxc,dbyc,dUf,dbxf,dbyf);
  for(size_t k=0;k<a.c.U.size();k++)a.c.U[k]=c0.U[k]+dt*dUc[k];
  for(size_t k=0;k<a.c.bx.size();k++)a.c.bx[k]=c0.bx[k]+dt*dbxc[k];
  for(size_t k=0;k<a.c.by.size();k++)a.c.by[k]=c0.by[k]+dt*dbyc[k];
  for(size_t k=0;k<a.f.U.size();k++)a.f.U[k]=f0.U[k]+dt*dUf[k];
  for(size_t k=0;k<a.f.bx.size();k++)a.f.bx[k]=f0.bx[k]+dt*dbxf[k];
  for(size_t k=0;k<a.f.by.size();k++)a.f.by[k]=f0.by[k]+dt*dbyf[k];
  restrictFineToCoarse(a);applyFloorGrid(a.c,nullptr);applyFloorGrid(a.f,&a.valid);
  computeRHS2(a,dUc,dbxc,dbyc,dUf,dbxf,dbyf);
  for(size_t k=0;k<a.c.U.size();k++)a.c.U[k]=0.5*(c0.U[k]+a.c.U[k]+dt*dUc[k]);
  for(size_t k=0;k<a.c.bx.size();k++)a.c.bx[k]=0.5*(c0.bx[k]+a.c.bx[k]+dt*dbxc[k]);
  for(size_t k=0;k<a.c.by.size();k++)a.c.by[k]=0.5*(c0.by[k]+a.c.by[k]+dt*dbyc[k]);
  for(size_t k=0;k<a.f.U.size();k++)a.f.U[k]=0.5*(f0.U[k]+a.f.U[k]+dt*dUf[k]);
  for(size_t k=0;k<a.f.bx.size();k++)a.f.bx[k]=0.5*(f0.bx[k]+a.f.bx[k]+dt*dbxf[k]);
  for(size_t k=0;k<a.f.by.size();k++)a.f.by[k]=0.5*(f0.by[k]+a.f.by[k]+dt*dbyf[k]);
  restrictFineToCoarse(a);applyFloorGrid(a.c,nullptr);applyFloorGrid(a.f,&a.valid);
}
// div-preserving prolongation of whole patch from coarse
static void computeAz0(Grid&c,vector<double>&Az){
  Az.assign((size_t)(c.NX+1)*(c.NY+1),0.0);
  auto A=[&](int I,int J)->double&{return Az[(size_t)J*(c.NX+1)+I];};
  for(int J=GH+1;J<=GH+c.ny;J++)A(GH,J)=A(GH,J-1)+c.bx[c.bxi(GH,J-1)]*c.dy;
  for(int J=GH;J<=GH+c.ny;J++)for(int I=GH+1;I<=GH+c.nx;I++)A(I,J)=A(I-1,J)-c.by[c.byi(I-1,J)]*c.dx;
}
static void prolongPatch(AMR&a,const set<pair<int,int>>&blocks){
  Grid&c=a.c,&f=a.f;vector<double> Az;computeAz0(c,Az);
  auto Ac=[&](int I,int J){return Az[(size_t)J*(c.NX+1)+I];};
  static vector<double> csx,csy;csx.assign((size_t)c.NX*c.NY*NV,0.0);csy.assign((size_t)c.NX*c.NY*NV,0.0);
  for(int J=1;J<c.NY-1;J++)for(int I=1;I<c.NX-1;I++)for(int v=0;v<NV;v++){double cc=c.U[c.cidx(I,J,v)];
    csx[(J*c.NX+I)*NV+v]=mclim(cc-c.U[c.cidx(I-1,J,v)],c.U[c.cidx(I+1,J,v)]-cc);
    csy[(J*c.NX+I)*NV+v]=mclim(cc-c.U[c.cidx(I,J-1,v)],c.U[c.cidx(I,J+1,v)]-cc);}
  int comps[6]={RHO,MX,MY,MZ,ENE,BZ};
  for(auto&b:blocks){int bi=b.first,bj=b.second;int I0=GH+(bi*a.BF)/2,J0=GH+(bj*a.BF)/2,ncI=a.BF/2;
    for(int cj=0;cj<ncI;cj++)for(int ci=0;ci<ncI;ci++){int I=I0+ci,J=J0+cj;int FI=GH+2*(I-GH),FJ=GH+2*(J-GH);
      double a00=Ac(I,J),a10=Ac(I+1,J),a01=Ac(I,J+1),a11=Ac(I+1,J+1);
      auto Af=[&](int s,int t){double u=s*0.5,vv=t*0.5;return (1-u)*(1-vv)*a00+u*(1-vv)*a10+(1-u)*vv*a01+u*vv*a11;};
      for(int s=0;s<=2;s++)for(int t=0;t<=1;t++)f.bx[f.bxi(FI+s,FJ+t)]=(Af(s,t+1)-Af(s,t))/f.dy;
      for(int s=0;s<=1;s++)for(int t=0;t<=2;t++)f.by[f.byi(FI+s,FJ+t)]=-(Af(s+1,t)-Af(s,t))/f.dx;
      for(int s=0;s<2;s++)for(int t=0;t<2;t++){int fi=FI+s,fj=FJ+t;double fx=(s-0.5)/2.0,fy=(t-0.5)/2.0;
        for(int cc=0;cc<6;cc++){int v=comps[cc];f.U[f.cidx(fi,fj,v)]=c.U[c.cidx(I,J,v)]+fx*csx[(J*c.NX+I)*NV+v]+fy*csy[(J*c.NX+I)*NV+v];}
        f.U[f.cidx(fi,fj,BX)]=f.Bxc(fi,fj);f.U[f.cidx(fi,fj,BY)]=f.Byc(fi,fj);}}}
}
// deterministic gradient-tagging refinement criterion + 1-block buffer dilation
static double REFTHR=0.2;
// scalar magnitude at a coarse cell used by the refinement indicator
static inline void primOf(Grid&c,int I,int J,double&rho,double&p,double&Bmag){
  double W[NV];cons2prim(&c.U[c.cidx(I,J,0)],W);rho=W[RHO];p=W[ENE];Bmag=sqrt(W[BX]*W[BX]+W[BY]*W[BY]+W[BZ]*W[BZ]);}
static set<pair<int,int>> computeBlocks(AMR&a){
  Grid&c=a.c;fillCellGhost(c,a.bc);
  // global scales (over uncovered coarse interior) so the indicator is resolution/amplitude robust
  double rhoS=1e-30,pS=1e-30,BS=1e-30;
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++){double r,p,b;primOf(c,I,J,r,p,b);rhoS=max(rhoS,fabs(r));pS=max(pS,fabs(p));BS=max(BS,fabs(b));}
  vector<char> tag((size_t)a.nbx*a.nby,0);
  for(int J=GH;J<GH+c.ny;J++)for(int I=GH;I<GH+c.nx;I++){
    double r,p,b,rxl,pxl,bxl,rxr,pxr,bxr,ryl,pyl,byl,ryr,pyr,byr;
    primOf(c,I,J,r,p,b);primOf(c,I-1,J,rxl,pxl,bxl);primOf(c,I+1,J,rxr,pxr,bxr);primOf(c,I,J-1,ryl,pyl,byl);primOf(c,I,J+1,ryr,pyr,byr);
    double cr=(fabs(rxr-rxl)+fabs(ryr-ryl))/(2*rhoS);
    double cp=(fabs(pxr-pxl)+fabs(pyr-pyl))/(2*pS);
    double cb=(fabs(bxr-bxl)+fabs(byr-byl))/(2*BS);
    double chi=max(max(cr,cp),cb);
    if(chi>=REFTHR){int fi=(I-GH)*2,fj=(J-GH)*2;int bi=fi/a.BF,bj=fj/a.BF;tag[bj*a.nbx+bi]=1;}}
  // dilate by 1 block (buffer) with bc-aware wrap
  vector<char> dil=tag;
  for(int bj=0;bj<a.nby;bj++)for(int bi=0;bi<a.nbx;bi++)if(tag[bj*a.nbx+bi])
    for(int db=-1;db<=1;db++)for(int da=-1;da<=1;da++){int nb=bi+da,nc=bj+db;
      if(a.bc==PER){nb=(nb+a.nbx)%a.nbx;nc=(nc+a.nby)%a.nby;}else{if(nb<0||nb>=a.nbx||nc<0||nc>=a.nby)continue;}
      dil[nc*a.nbx+nb]=1;}
  set<pair<int,int>> out;
  for(int bj=0;bj<a.nby;bj++)for(int bi=0;bi<a.nbx;bi++)if(dil[bj*a.nbx+bi])out.insert({bi,bj});
  return out;
}
static void regrid(AMR&a){
  fillCellGhost(a.c,a.bc);fillFaceGhost(a.c,a.bc);
  set<pair<int,int>> nb=computeBlocks(a);
  for(auto&b:nb)if(!a.blocks.count(b))blocksCreated++;
  for(auto&b:a.blocks)if(!nb.count(b))blocksDeleted++;
  prolongPatch(a,nb);a.blocks=nb;rebuildMasks(a);
  long n=(long)a.blocks.size();if(n>nblocksMax)nblocksMax=n;if(nblocksMin<0||n<nblocksMin)nblocksMin=n;
  // prolongation interpolates conserved E and B independently, so a freshly refined cell can
  // carry a non-positive pressure even when its parents are positive; restore positivity.
  applyFloorGrid(a.f,&a.valid);
}

// ================= presets =================
static double ALPHA=M_PI/4,AMP=0.1,KMAG,B0=1.0,CX=0.5,CY=0.5,PCEN=10.0,PAMB=0.1,VAC_V=3.0,LVX=2.0,LVY=1.0,RS_BPAR=0.5,RS_BPERP=0.5,RS_RHOL=1.0,RS_RHOR=0.4,RS_PL=1.0,RS_PR=0.4;
static int PRESET=0; // 0 cpaw,1 field_loop,2 blast,3 vacuum,4 rotated_shock
static double cpawAz(double x,double y){double nx=cos(ALPHA),ny=sin(ALPHA);double kr=KMAG*(nx*x+ny*y);return B0*(nx*y-ny*x)+(AMP/KMAG)*cos(kr);}
static void cpawCell(double x,double y,double t,double*W){double nx=cos(ALPHA),ny=sin(ALPHA);double va=B0/sqrt(1.0);
  double phi=KMAG*(nx*x+ny*y)-KMAG*va*t;double px=-ny,py=nx;double Bp=AMP*sin(phi),Bz=AMP*cos(phi);
  double Bx=B0*nx+Bp*px,By=B0*ny+Bp*py;double vp=-AMP*sin(phi),vz=-AMP*cos(phi);
  W[RHO]=1.0;W[MX]=vp*px;W[MY]=vp*py;W[MZ]=vz;W[ENE]=0.1;W[BX]=Bx;W[BY]=By;W[BZ]=Bz;}
static double loopAz(double x,double y,double Lx,double Ly){
  // nearest periodic image of center
  double dx=x-CX*Lx,dy=y-CY*Ly; double R=0.3*min(Lx,Ly);
  double r=sqrt(dx*dx+dy*dy); return (r<R)?AMP*(R-r):0.0;}
static double vacBy=0.0;
// generic Az for a grid, per preset (returns Az value used to set div-free faces)
static double presetAz(double x,double y,double Lx,double Ly){
  if(PRESET==0)return cpawAz(x,y);
  if(PRESET==1)return loopAz(x,y,Lx,Ly);
  if(PRESET==2){double nx=cos(M_PI/4),ny=sin(M_PI/4);return B0*(nx*y-ny*x);} // uniform diagonal field
  if(PRESET==3)return -vacBy*x; // uniform By
  if(PRESET==4){ // rotated (oblique) shock: parallel field B0 along n + transverse step via
    // piecewise-linear vector potential g(xi) (kink at the interface -> B_perp flips sign, div-free).
    double nx=cos(ALPHA),ny=sin(ALPHA);double xi=nx*x+ny*y;double xi0=(nx*Lx+ny*Ly)*0.5;
    double gg=-RS_BPERP*((xi<xi0)?(xi-xi0):-(xi-xi0));
    return RS_BPAR*(nx*y-ny*x)+gg;
  }
  return 0.0;
}
static void presetCell(double x,double y,double Lx,double Ly,double*W){
  for(int v=0;v<NV;v++)W[v]=0; W[RHO]=1;W[ENE]=1;
  if(PRESET==0){cpawCell(x,y,0,W);return;}
  if(PRESET==1){W[RHO]=1;W[ENE]=1;W[MX]=LVX;W[MY]=LVY;W[MZ]=0;W[BZ]=0;return;}
  if(PRESET==2){double dx=x-CX*Lx,dy=y-CY*Ly;double r=sqrt(dx*dx+dy*dy);
    W[RHO]=1;W[ENE]=(r<0.1*min(Lx,Ly))?PCEN:PAMB;W[MX]=W[MY]=W[MZ]=0;W[BZ]=0;return;}
  if(PRESET==3){W[RHO]=1;W[ENE]=0.4;double xc=x/Lx;W[MX]=(xc<0.5)?-VAC_V:VAC_V;W[MY]=0;W[MZ]=0;W[BZ]=0;return;}
  if(PRESET==4){double nx=cos(ALPHA),ny=sin(ALPHA);double xi=nx*x+ny*y;double xi0=(nx*Lx+ny*Ly)*0.5;
    bool L=(xi<xi0);W[RHO]=L?RS_RHOL:RS_RHOR;W[ENE]=L?RS_PL:RS_PR;W[MX]=W[MY]=W[MZ]=0;W[BZ]=0;return;}
}
static void initGrid(Grid&g){
  double Lx=g.Lx,Ly=g.Ly;
  for(int j=0;j<g.NY;j++)for(int i=0;i<=g.NX;i++){double x=(i-GH)*g.dx,yb=(j-GH)*g.dy,yt=(j-GH+1)*g.dy;g.bx[g.bxi(i,j)]=(presetAz(x,yt,Lx,Ly)-presetAz(x,yb,Lx,Ly))/g.dy;}
  for(int j=0;j<=g.NY;j++)for(int i=0;i<g.NX;i++){double y=(j-GH)*g.dy,xl=(i-GH)*g.dx,xr=(i-GH+1)*g.dx;g.by[g.byi(i,j)]=-(presetAz(xr,y,Lx,Ly)-presetAz(xl,y,Lx,Ly))/g.dx;}
  for(int j=0;j<g.NY;j++)for(int i=0;i<g.NX;i++){double x=(i-GH+0.5)*g.dx,y=(j-GH+0.5)*g.dy;double W[NV];presetCell(x,y,Lx,Ly,W);double U[NV];prim2cons(W,U);
    g.U[g.cidx(i,j,RHO)]=U[RHO];g.U[g.cidx(i,j,MX)]=U[MX];g.U[g.cidx(i,j,MY)]=U[MY];g.U[g.cidx(i,j,MZ)]=U[MZ];g.U[g.cidx(i,j,ENE)]=U[ENE];g.U[g.cidx(i,j,BZ)]=U[BZ];}
}

// ================= diagnostics + IO =================
static double maxDivBGrid(Grid&g,const vector<char>*mask){double m=0;
  for(int j=GH;j<GH+g.ny;j++)for(int i=GH;i<GH+g.nx;i++){if(mask&&!(*mask)[j*g.NX+i])continue;
    double d=(g.bx[g.bxi(i+1,j)]-g.bx[g.bxi(i,j)])/g.dx+(g.by[g.byi(i,j+1)]-g.by[g.byi(i,j)])/g.dy;m=max(m,fabs(d));}return m;}
static void totals(AMR&a,double*T,double&magE){for(int v=0;v<NV;v++)T[v]=0;magE=0;double da0=a.c.dx*a.c.dy,da1=a.f.dx*a.f.dy;
  for(int J=GH;J<GH+a.c.ny;J++)for(int I=GH;I<GH+a.c.nx;I++)if(!a.covered[J*a.c.NX+I]){for(int v=0;v<NV;v++)T[v]+=a.c.U[a.c.cidx(I,J,v)]*da0;
    double bx=a.c.Bxc(I,J),by=a.c.Byc(I,J),bz=a.c.U[a.c.cidx(I,J,BZ)];magE+=0.5*(bx*bx+by*by+bz*bz)*da0;}
  for(int J=GH;J<GH+a.f.ny;J++)for(int I=GH;I<GH+a.f.nx;I++)if(a.valC(I,J)){for(int v=0;v<NV;v++)T[v]+=a.f.U[a.f.cidx(I,J,v)]*da1;
    double bx=a.f.Bxc(I,J),by=a.f.Byc(I,J),bz=a.f.U[a.f.cidx(I,J,BZ)];magE+=0.5*(bx*bx+by*by+bz*bz)*da1;}}
static void minRhoP(AMR&a,double&mr,double&mp){mr=1e30;mp=1e30;
  for(int J=GH;J<GH+a.c.ny;J++)for(int I=GH;I<GH+a.c.nx;I++)if(!a.covered[J*a.c.NX+I]){double W[NV];cons2prim(&a.c.U[a.c.cidx(I,J,0)],W);mr=min(mr,W[RHO]);mp=min(mp,W[ENE]);}
  for(int J=GH;J<GH+a.f.ny;J++)for(int I=GH;I<GH+a.f.nx;I++)if(a.valC(I,J)){double W[NV];cons2prim(&a.f.U[a.f.cidx(I,J,0)],W);mr=min(mr,W[RHO]);mp=min(mp,W[ENE]);}}

static void emitArr(ostream&o,const char*name,const vector<double>&v){o<<"\""<<name<<"\":[";char b[32];
  for(size_t k=0;k<v.size();k++){snprintf(b,sizeof b,"%.17g",v[k]);o<<b;if(k+1<v.size())o<<',';}o<<"]";}
static void gridCellArrays(Grid&g,vector<double>&rho,vector<double>&u,vector<double>&vv,vector<double>&w,vector<double>&p,vector<double>&bz){
  int nx=g.nx,ny=g.ny;rho.resize(nx*ny);u.resize(nx*ny);vv.resize(nx*ny);w.resize(nx*ny);p.resize(nx*ny);bz.resize(nx*ny);
  for(int j=0;j<ny;j++)for(int i=0;i<nx;i++){double W[NV];cons2prim(&g.U[g.cidx(i+GH,j+GH,0)],W);int k=j*nx+i;
    rho[k]=W[RHO];u[k]=W[MX];vv[k]=W[MY];w[k]=W[MZ];p[k]=W[ENE];bz[k]=W[BZ];}}
static void faceArrays(Grid&g,int i0,int j0,int nx,int ny,vector<double>&bxo,vector<double>&byo){
  bxo.resize((nx+1)*ny);byo.resize(nx*(ny+1));
  for(int j=0;j<ny;j++)for(int i=0;i<=nx;i++)bxo[j*(nx+1)+i]=g.bx[g.bxi(i0+i,j0+j)];
  for(int j=0;j<=ny;j++)for(int i=0;i<nx;i++)byo[j*nx+i]=g.by[g.byi(i0+i,j0+j)];}

static double cpawL1(AMR&a,double t){double s=0;long cnt=0;Grid&g=a.c;
  for(int j=GH;j<GH+g.ny;j++)for(int i=GH;i<GH+g.nx;i++){if(a.covered[j*g.NX+i])continue;double x=(i-GH+0.5)*g.dx,y=(j-GH+0.5)*g.dy;double W[NV];cpawCell(x,y,t,W);
    s+=fabs(g.Bxc(i,j)-W[BX])+fabs(g.Byc(i,j)-W[BY])+fabs(g.U[g.cidx(i,j,BZ)]-W[BZ]);cnt++;}
  for(int j=GH;j<GH+a.f.ny;j++)for(int i=GH;i<GH+a.f.nx;i++)if(a.valC(i,j)){double x=(i-GH+0.5)*a.f.dx,y=(j-GH+0.5)*a.f.dy;double W[NV];cpawCell(x,y,t,W);
    s+=fabs(a.f.Bxc(i,j)-W[BX])+fabs(a.f.Byc(i,j)-W[BY])+fabs(a.f.U[a.f.cidx(i,j,BZ)]-W[BZ]);cnt++;}
  return s/cnt;}

// ---- checkpoint (text) ----
static void writeCheckpoint(AMR&a,double t,int step,const string&path){
  ofstream o(path);o.precision(17);o.setf(ios::scientific);o<<"AMRMHD_CKPT 1\n";
  o<<a.c.nx<<" "<<a.c.ny<<" "<<a.c.Lx<<" "<<a.c.Ly<<" "<<a.BF<<" "<<a.bc<<" "<<PRESET<<" "<<step<<" ";
  char b[40];snprintf(b,sizeof b,"%.17g",t);o<<b<<" "<<GAM<<"\n";
  o<<a.blocks.size()<<"\n";for(auto&bl:a.blocks)o<<bl.first<<" "<<bl.second<<"\n";
  auto dump=[&](const vector<double>&v){for(size_t k=0;k<v.size();k++){snprintf(b,sizeof b,"%.17g",v[k]);o<<b<<((k+1<v.size())?' ':'\n');}};
  dump(a.c.U);dump(a.c.bx);dump(a.c.by);dump(a.f.U);dump(a.f.bx);dump(a.f.by);
}
static bool readCheckpoint(AMR&a,double&t,int&step,const string&path){
  ifstream in(path);if(!in)return false;string mg;int ver;in>>mg>>ver;if(mg!="AMRMHD_CKPT")return false;
  int nx,ny,bf,bc,pr;double Lx,Ly,g;in>>nx>>ny>>Lx>>Ly>>bf>>bc>>pr>>step>>t>>g;GAM=g;PRESET=pr;
  a.BF=bf;a.bc=bc;alloc(a.c,nx,ny,Lx,Ly);alloc(a.f,2*nx,2*ny,Lx,Ly);a.nbx=(2*nx)/bf;a.nby=(2*ny)/bf;
  size_t nb;in>>nb;a.blocks.clear();for(size_t k=0;k<nb;k++){int bi,bj;in>>bi>>bj;a.blocks.insert({bi,bj});}
  auto load=[&](vector<double>&v){for(size_t k=0;k<v.size();k++)in>>v[k];};
  load(a.c.U);load(a.c.bx);load(a.c.by);load(a.f.U);load(a.f.bx);load(a.f.by);rebuildMasks(a);return true;}

static void writeResult(AMR&a,double t,int step,double*T0,double magE0,const string&path,double l1){
  double T1[NV],magE1;totals(a,T1,magE1);double mr,mp;minRhoP(a,mr,mp);
  double dc=maxDivBGrid(a.c,nullptr),df=maxDivBGrid(a.f,&a.valid);
  ofstream o(path);o<<"{";
  o<<"\"preset\":"<<PRESET<<",\"bc\":"<<a.bc<<",\"nx\":"<<a.c.nx<<",\"ny\":"<<a.c.ny;
  char b[40];o<<",\"Lx\":"<<a.c.Lx<<",\"Ly\":"<<a.c.Ly<<",\"block\":"<<a.BF<<",\"gamma\":"<<GAM;
  snprintf(b,sizeof b,"%.17g",t);o<<",\"t\":"<<b<<",\"steps\":"<<step;
  o<<",\"nblocks\":"<<a.blocks.size();
  // canonical block order: ascending bj, then ascending bi
  vector<pair<int,int>> ord;for(auto&bl:a.blocks)ord.push_back({bl.second,bl.first});sort(ord.begin(),ord.end());
  o<<",\"block_order\":[";int kk=0;for(auto&p:ord){o<<"["<<p.second<<","<<p.first<<"]";if(++kk<(int)ord.size())o<<",";}o<<"]";
  auto sc=[&](const char*n,double val){snprintf(b,sizeof b,"%.17g",val);o<<",\""<<n<<"\":"<<b;};
  sc("mass0",T0[RHO]);sc("momx0",T0[MX]);sc("momy0",T0[MY]);sc("momz0",T0[MZ]);sc("energy0",T0[ENE]);sc("magE0",magE0);
  sc("mass",T1[RHO]);sc("momx",T1[MX]);sc("momy",T1[MY]);sc("momz",T1[MZ]);sc("energy",T1[ENE]);sc("magE",magE1);
  sc("min_rho",mr);sc("min_p",mp);sc("maxdivB_coarse",dc);sc("maxdivB_fine",df);sc("l1",l1);
  o<<",\"protect\":"<<protectCount;
  o<<",\"blocks_created\":"<<blocksCreated<<",\"blocks_deleted\":"<<blocksDeleted<<",\"nblocks_max\":"<<(nblocksMax<0?0:nblocksMax)<<",\"nblocks_min\":"<<(nblocksMin<0?0:nblocksMin);
  // coarse fields
  vector<double> rho,u,vv,w,p,bz,bxo,byo;gridCellArrays(a.c,rho,u,vv,w,p,bz);faceArrays(a.c,GH,GH,a.c.nx,a.c.ny,bxo,byo);
  o<<",\"coarse\":{";emitArr(o,"rho",rho);o<<",";emitArr(o,"u",u);o<<",";emitArr(o,"v",vv);o<<",";emitArr(o,"w",w);o<<",";emitArr(o,"p",p);o<<",";emitArr(o,"bz",bz);o<<",";emitArr(o,"bx",bxo);o<<",";emitArr(o,"by",byo);o<<"}";
  // blocks in canonical (bj,bi) order
  o<<",\"blocks\":[";kk=0;
  for(auto&pr:ord){int bi=pr.second,bj=pr.first;int fi0=GH+bi*a.BF,fj0=GH+bj*a.BF;int bf=a.BF;
    vector<double> r2,u2,v2,w2,p2,z2;int nx=bf,ny=bf;r2.resize(nx*ny);u2.resize(nx*ny);v2.resize(nx*ny);w2.resize(nx*ny);p2.resize(nx*ny);z2.resize(nx*ny);
    for(int j=0;j<ny;j++)for(int i=0;i<nx;i++){double W[NV];cons2prim(&a.f.U[a.f.cidx(fi0+i,fj0+j,0)],W);int k=j*nx+i;r2[k]=W[RHO];u2[k]=W[MX];v2[k]=W[MY];w2[k]=W[MZ];p2[k]=W[ENE];z2[k]=W[BZ];}
    vector<double> bx2,by2;faceArrays(a.f,fi0,fj0,bf,bf,bx2,by2);
    o<<"{\"bi\":"<<bi<<",\"bj\":"<<bj<<",\"bf\":"<<bf<<",";emitArr(o,"rho",r2);o<<",";emitArr(o,"u",u2);o<<",";emitArr(o,"v",v2);o<<",";emitArr(o,"w",w2);o<<",";emitArr(o,"p",p2);o<<",";emitArr(o,"bz",z2);o<<",";emitArr(o,"bx",bx2);o<<",";emitArr(o,"by",by2);o<<"}";
    if(++kk<(int)ord.size())o<<",";}
  o<<"]}";
}

// ================= case parse + main =================
static map<string,string> parseCase(const string&path){map<string,string> m;ifstream in(path);string line;
  while(getline(in,line)){size_t h=line.find('#');if(h!=string::npos)line=line.substr(0,h);
    size_t eq=line.find('=');if(eq==string::npos)continue;string k=line.substr(0,eq),v=line.substr(eq+1);
    auto trim=[](string&s){size_t a=s.find_first_not_of(" \t\r\n");size_t b=s.find_last_not_of(" \t\r\n");if(a==string::npos){s="";return;}s=s.substr(a,b-a+1);};
    trim(k);trim(v);if(!k.empty())m[k]=v;}return m;}
static double gd(map<string,string>&m,const char*k,double def){auto it=m.find(k);return it==m.end()?def:atof(it->second.c_str());}
static int gi(map<string,string>&m,const char*k,int def){auto it=m.find(k);return it==m.end()?def:atoi(it->second.c_str());}
static string gs(map<string,string>&m,const char*k,const char*def){auto it=m.find(k);return it==m.end()?string(def):it->second;}

int main(int argc,char**argv){
  string casef,outf="result.json",restart="",ckptOut="";int ckptAt=-1;
  for(int i=1;i<argc;i++){string s=argv[i];
    if(s=="--case"&&i+1<argc)casef=argv[++i];
    else if(s=="--out"&&i+1<argc)outf=argv[++i];
    else if(s=="--restart"&&i+1<argc)restart=argv[++i];
    else if(s=="--checkpoint-out"&&i+1<argc)ckptOut=argv[++i];
    else if(s=="--checkpoint-at"&&i+1<argc)ckptAt=atoi(argv[++i]);}
  AMR a;double t=0;int step=0;int nsteps=0;double tmax=0;double cfl=0.4;int regridInterval=0;bool amr=true;
  if(!restart.empty()){
    if(!readCheckpoint(a,t,step,restart)){fprintf(stderr,"bad checkpoint\n");return 2;}
    // read remaining run controls from case (tmax/nsteps/regrid)
  }
  map<string,string> m;if(!casef.empty())m=parseCase(casef);
  cfl=gd(m,"cfl",0.4);regridInterval=gi(m,"regrid_interval",0);amr=gi(m,"amr",1)!=0;
  nsteps=gi(m,"nsteps",0);tmax=gd(m,"tmax",0.0);REFTHR=gd(m,"refine_threshold",0.2);
  GAM=gd(m,"gamma",restart.empty()?5.0/3.0:GAM);
  if(restart.empty()){
    int nx=gi(m,"nx",32),ny=gi(m,"ny",32);double Lx=gd(m,"Lx",1.0),Ly=gd(m,"Ly",1.0);int bf=gi(m,"block",8);
    string pr=gs(m,"preset","cpaw");
    PRESET=(pr=="cpaw")?0:(pr=="field_loop")?1:(pr=="blast")?2:(pr=="vacuum")?3:(pr=="rotated_shock")?4:0;
    a.bc=(gs(m,"bc",(PRESET==4)?"outflow":"periodic")=="outflow")?OUTF:PER;
    ALPHA=gd(m,"alpha",M_PI/4);AMP=gd(m,"amp",(PRESET==0)?0.1:(PRESET==1?1e-3:1.0));
    B0=gd(m,"B0",1.0);CX=gd(m,"cx",0.5);CY=gd(m,"cy",0.5);vacBy=gd(m,"vac_by",0.0);
    PCEN=gd(m,"p_center",10.0);PAMB=gd(m,"p_ambient",0.1);VAC_V=gd(m,"vac_v",3.0);LVX=gd(m,"lvx",2.0);LVY=gd(m,"lvy",1.0);RS_BPAR=gd(m,"rs_bpar",0.5);RS_BPERP=gd(m,"rs_bperp",0.5);RS_RHOL=gd(m,"rs_rhoL",1.0);RS_RHOR=gd(m,"rs_rhoR",0.4);RS_PL=gd(m,"rs_pL",1.0);RS_PR=gd(m,"rs_pR",0.4);
    KMAG=2*M_PI*sqrt(2.0);
    a.BF=bf;a.nbx=(2*nx)/bf;a.nby=(2*ny)/bf;alloc(a.c,nx,ny,Lx,Ly);alloc(a.f,2*nx,2*ny,Lx,Ly);
    initGrid(a.c);initGrid(a.f);fillCellGhost(a.c,a.bc);fillFaceGhost(a.c,a.bc);
    a.blocks.clear();rebuildMasks(a);
    // An explicit "blocks = bi,bj bi,bj ..." list pins the active set instead of deriving it
    // from the refinement indicator; with regrid_interval = 0 it stays fixed for the whole run.
    string bl=gs(m,"blocks","");
    if(amr&&!bl.empty()){
      set<pair<int,int>> req;istringstream ss(bl);string tok;
      while(ss>>tok){size_t cm=tok.find(',');if(cm==string::npos)continue;
        int bi=atoi(tok.substr(0,cm).c_str()),bj=atoi(tok.substr(cm+1).c_str());
        if(bi>=0&&bi<a.nbx&&bj>=0&&bj<a.nby)req.insert({bi,bj});}
      fillCellGhost(a.c,a.bc);fillFaceGhost(a.c,a.bc);
      for(auto&b:req)blocksCreated++;
      prolongPatch(a,req);a.blocks=req;rebuildMasks(a);applyFloorGrid(a.f,&a.valid);
      long n=(long)a.blocks.size();if(n>nblocksMax)nblocksMax=n;if(nblocksMin<0||n<nblocksMin)nblocksMin=n;
    } else if(amr){regrid(a);} // initial refinement from the indicator
  } else {
    // restart: preset params for cpaw analytic / az already restored; set derived
    ALPHA=gd(m,"alpha",M_PI/4);AMP=gd(m,"amp",(PRESET==0)?0.1:(PRESET==1?1e-3:1.0));B0=gd(m,"B0",1.0);KMAG=2*M_PI*sqrt(2.0);
  }
  double T0[NV],magE0;totals(a,T0,magE0);
  // for restart we still want conservation reference of the ORIGINAL run; store from checkpoint? keep current as ref.
  int startStep=step;
  auto stop=[&](){ if(nsteps>0)return step>=nsteps; if(tmax>0)return t>=tmax-1e-12; return step>=100; };
  while(!stop()){
    double dt=dtCFL2(a,cfl); if(tmax>0&&t+dt>tmax)dt=tmax-t;
    step2(a,dt);t+=dt;step++;
    if(amr&&regridInterval>0&&(step%regridInterval==0))regrid(a);
    if(ckptAt>0&&step==ckptAt&&!ckptOut.empty())writeCheckpoint(a,t,step,ckptOut);
  }
  // Finalize: make cell-centered B consistent with the (output) face fields, and enforce
  // positivity, so the reported primitive state matches the emitted staggered fields exactly.
  fillCellGhost(a.c,a.bc);
  for(int J=GH;J<GH+a.f.ny;J++)for(int I=GH;I<GH+a.f.nx;I++)if(a.valC(I,J)){a.f.U[a.f.cidx(I,J,BX)]=a.f.Bxc(I,J);a.f.U[a.f.cidx(I,J,BY)]=a.f.Byc(I,J);}
  applyFloorGrid(a.c,nullptr);applyFloorGrid(a.f,&a.valid);
  double l1=(PRESET==0)?cpawL1(a,t):0.0;
  writeResult(a,t,step,T0,magE0,outf,l1);
  return 0;
}
AMR_MHD_EOF

make clean >/dev/null 2>&1 || true
make

echo "[solve] build complete; running self-checks"
python3 - <<'PYEOF'
import json, subprocess, math
import numpy as np
BIN = "/app/bin/amr_mhd"

def run(txt, out, extra=None):
    open("/tmp/sc_case.txt", "w").write(txt)
    r = subprocess.run([BIN, "--case", "/tmp/sc_case.txt", "--out", out] + (extra or []),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.load(open(out))

def divB_coarse(d):
    nx, ny = d["nx"], d["ny"]; dx, dy = d["Lx"]/nx, d["Ly"]/ny
    bx = np.array(d["coarse"]["bx"]).reshape(ny, nx+1)
    by = np.array(d["coarse"]["by"]).reshape(ny+1, nx)
    cov = np.zeros((ny, nx), bool); bf = d["block"]
    for b in d["blocks"]:
        i0 = b["bi"]*bf//2; j0 = b["bj"]*bf//2; n = bf//2
        cov[j0:j0+n, i0:i0+n] = True
    div = (bx[:, 1:]-bx[:, :-1])/dx + (by[1:, :]-by[:-1, :])/dy
    return float(np.max(np.abs(div[~cov]))) if (~cov).any() else 0.0

def divB_fine(d):
    m = 0.0; bf = d["block"]; dx = d["Lx"]/d["nx"]/2; dy = d["Ly"]/d["ny"]/2
    for b in d["blocks"]:
        bx = np.array(b["bx"]).reshape(bf, bf+1); by = np.array(b["by"]).reshape(bf+1, bf)
        div = (bx[:, 1:]-bx[:, :-1])/dx + (by[1:, :]-by[:-1, :])/dy
        m = max(m, float(np.max(np.abs(div))))
    return m

# second-order convergence on the smooth Alfven wave
errs = [run(f"preset=cpaw\nnx={N}\nny={N}\namr=0\ntmax=0.3\n", "/tmp/sc.json")["l1"] for N in (32, 64)]
order = math.log(errs[0]/errs[1]) / math.log(2)
assert order > 1.8, ("convergence order too low", order)

# machine-zero divergence on both levels + conservation with refluxing (periodic AMR)
d = run("preset=field_loop\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=1000\n"
        "refine_threshold=0.25\ntmax=0.1\nlvx=1.0\nlvy=0.5\n", "/tmp/sc.json")
assert d["nblocks"] > 0, "field loop did not refine"
assert divB_coarse(d) < 1e-9 and divB_fine(d) < 1e-9, "divergence not machine-zero"
assert abs(d["energy"]-d["energy0"]) < 1e-8 and abs(d["mass"]-d["mass0"]) < 1e-8, "not conserved"

# positivity through a strong blast
d = run("preset=blast\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=5\nrefine_threshold=0.3\n"
        "tmax=0.06\nB0=0.5\np_center=10\np_ambient=0.5\n", "/tmp/sc.json")
assert d["min_rho"] > 0 and d["min_p"] > 0, "positivity violated"

# bit-exact restart across a regrid
common = "preset=blast\nnx=32\nny=32\nblock=8\namr=1\nregrid_interval=5\nrefine_threshold=0.3\ncfl=0.4\n"
full = run(common + "nsteps=20\n", "/tmp/scf.json")
run(common + "nsteps=10\n", "/tmp/sch.json", ["--checkpoint-out", "/tmp/sc.ckpt", "--checkpoint-at", "10"])
cont = run(common + "nsteps=20\n", "/tmp/scc.json", ["--restart", "/tmp/sc.ckpt"])
diff = np.max(np.abs(np.array(full["coarse"]["rho"]) - np.array(cont["coarse"]["rho"])))
assert diff < 1e-12, ("restart not reproducible", diff)


# a pinned layout straddling both periodic seams must stay exactly coupled
d = run("preset=cpaw\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=0\ncfl=0.4\ntmax=0.2\n"
        "blocks=11,11 0,11 11,0 0,0\n", "/tmp/scg.json")
assert d["nblocks"] == 4, "pinned layout was not honoured"
assert divB_coarse(d) < 1e-9 and divB_fine(d) < 1e-9, "seam-straddling layout broke the divergence"
assert abs(d["energy"] - d["energy0"]) < 1e-8, "seam-straddling layout broke conservation"

print("[solve] self-checks passed (order=%.3f)" % order)
PYEOF

echo "[solve] done"

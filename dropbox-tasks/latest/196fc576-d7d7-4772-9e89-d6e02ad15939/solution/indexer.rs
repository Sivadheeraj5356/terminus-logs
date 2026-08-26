use std::collections::{BTreeMap, BTreeSet};
use crate::model::{Objective, Plan, ScanPlan, Shell, Study};

const MOD:i64=1_000_000_007;

fn phase_rank(c:char)->i32{match c{'P'=>0,'I'=>1,_=>2}}
fn allowed(c:char,h:i32,k:i32,l:i32)->bool{match c{'P'=>true,'I'=>(h+k+l)%2==0,'F'=>(h%2==k%2)&&(k%2==l%2),_=>false}}
fn shells(study:&Study,phase:char)->Vec<Shell>{
    let mut m:BTreeMap<i32,(i32,i32,i32)>=BTreeMap::new();
    for h in 0..=study.hmax { for k in 0..=h { for l in 0..=k { if h==0&&k==0&&l==0{continue;} if !allowed(phase,h,k,l){continue;} let n=h*h+k*k+l*l; let t=(h,k,l); match m.get(&n){Some(old) if *old<=t=>{},_=>{m.insert(n,t);}} }}}
    m.into_iter().map(|(n,(h,k,l))|Shell{n,h,k,l}).collect()
}

fn enumerate_scan(study:&Study, si:usize, shells:&[Shell], a:i64,z:i64)->Vec<ScanPlan>{
    let scan=&study.scans[si]; let mut out=Vec::new(); let mut assign=vec![0i32;scan.peaks.len()];
    fn rec(study:&Study,si:usize,shells:&[Shell],a:i64,z:i64,i:usize,last:i32,imp:usize,assign:&mut Vec<i32>,out:&mut Vec<ScanPlan>){
        let scan=&study.scans[si]; if i==scan.peaks.len(){
            if imp>study.max_impurities{return;}
            let used:BTreeSet<i32>=assign.iter().copied().filter(|x|*x>0).collect();
            let mut missing=Vec::new(); if let (Some(lo),Some(hi))=(used.iter().next(),used.iter().next_back()){
                for sh in shells { let pred=a*sh.n as i64+z; if sh.n>*lo&&sh.n<*hi&&pred>=study.scan_lo&&pred<=study.scan_hi&&!used.contains(&sh.n){missing.push(sh.n);} }
            }
            if missing.len()>study.max_missing{return;}
            let mut residual=0; let mut weight=0; for (j,n) in assign.iter().enumerate(){ if *n>0 { let p=&scan.peaks[j]; residual+=(p.q-(a*(*n as i64)+z)).abs(); weight+=p.weight; }}
            out.push(ScanPlan{assign:assign.clone(),missing,residual,weight}); return;
        }
        if imp<study.max_impurities {assign[i]=0;rec(study,si,shells,a,z,i+1,last,imp+1,assign,out);}
        let p=&scan.peaks[i]; for sh in shells { if sh.n<=last{continue;} let pred=a*sh.n as i64+z; if (p.q-pred).abs()<=p.tol {assign[i]=sh.n;rec(study,si,shells,a,z,i+1,sh.n,imp,assign,out);} }
    }
    rec(study,si,shells,a,z,0,0,0,&mut assign,&mut out); out
}
fn objective(p0:&ScanPlan,p1:&ScanPlan,a:[i64;2],z:[i64;2])->Objective{
    let s0:BTreeSet<i32>=p0.assign.iter().copied().filter(|x|*x>0).collect(); let s1:BTreeSet<i32>=p1.assign.iter().copied().filter(|x|*x>0).collect();
    let consensus=s0.intersection(&s1).count(); let orphans=s0.symmetric_difference(&s1).count();
    Objective{indexed_weight:p0.weight+p1.weight,consensus,residual:p0.residual+p1.residual,missing:p0.missing.len()+p1.missing.len(),orphans,motion:(a[1]-a[0]).abs()+(z[1]-z[0]).abs()}
}
fn num_cmp(a:&Objective,b:&Objective)->std::cmp::Ordering{
    b.indexed_weight.cmp(&a.indexed_weight).then_with(||b.consensus.cmp(&a.consensus)).then_with(||a.residual.cmp(&b.residual)).then_with(||a.missing.cmp(&b.missing)).then_with(||a.orphans.cmp(&b.orphans)).then_with(||a.motion.cmp(&b.motion))
}
fn canon_key(phase:char,a:[i64;2],z:[i64;2],p0:&ScanPlan,p1:&ScanPlan)->(i32,i64,i64,i64,i64,Vec<i32>,Vec<i32>){(phase_rank(phase),a[0],z[0],a[1],z[1],p0.assign.clone(),p1.assign.clone())}

pub fn solve(study: &Study) -> Option<Plan> {
    let mut best: Option<Plan> = None;
    let mut count = 0i64;
    for &phase in &study.phases {
        let sh = shells(study, phase);
        for a0 in study.scale_min..=study.scale_max {
            for a1 in study.scale_min..=study.scale_max {
                if (a1 - a0).abs() > study.drift { continue; }
                for z0 in study.shift_min..=study.shift_max {
                    let c0 = enumerate_scan(study, 0, &sh, a0, z0);
                    if c0.is_empty() { continue; }
                    for z1 in study.shift_min..=study.shift_max {
                        let c1 = enumerate_scan(study, 1, &sh, a1, z1);
                        if c1.is_empty() { continue; }
                        for p0 in &c0 {
                            for p1 in &c1 {
                                let obj = objective(p0, p1, [a0, a1], [z0, z1]);
                                if obj.consensus < study.min_consensus { continue; }
                                let candidate = Plan {
                                    phase,
                                    a: [a0, a1],
                                    z: [z0, z1],
                                    scans: [p0.clone(), p1.clone()],
                                    objective: obj,
                                    optimal_count: 1,
                                    shells: sh.clone(),
                                };
                                match best.as_ref() {
                                    None => { best = Some(candidate); count = 1; }
                                    Some(current) => match num_cmp(&candidate.objective, &current.objective) {
                                        std::cmp::Ordering::Less => { best = Some(candidate); count = 1; }
                                        std::cmp::Ordering::Equal => {
                                            count = (count + 1) % MOD;
                                            let ck = canon_key(candidate.phase, candidate.a, candidate.z, &candidate.scans[0], &candidate.scans[1]);
                                            let bk = canon_key(current.phase, current.a, current.z, &current.scans[0], &current.scans[1]);
                                            if ck < bk { best = Some(candidate); }
                                        }
                                        std::cmp::Ordering::Greater => {}
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    best.map(|mut plan| { plan.optimal_count = count; plan })
}

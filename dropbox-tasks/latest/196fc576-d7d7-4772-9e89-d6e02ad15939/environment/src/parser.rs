use crate::model::{Peak, Scan, Study};

fn ident(s:&str)->bool { let mut c=s.chars(); match c.next(){Some(x) if x.is_ascii_alphabetic()=>{},_=>return false}; s.len()<=32 && c.all(|x|x.is_ascii_alphanumeric()||x=='_'||x=='-') }
fn num(s:&str)->Result<i64,&'static str>{ s.parse::<i64>().map_err(|_|"BAD_NUMBER") }
pub fn parse(input:&str)->Result<Study,(usize,&'static str)> {
    let mut rows:Vec<(usize,Vec<&str>)>=Vec::new();
    for (i,line) in input.lines().enumerate(){ let t=line.trim_end_matches('\r').trim(); if !t.is_empty(){ rows.push((i+1,t.split_whitespace().collect())); }}
    let mut p=0usize;
    macro_rules! row {()=>{{ if p>=rows.len(){return Err((input.lines().count()+1,"UNEXPECTED_EOF"));} let r=&rows[p]; p+=1; r }};}
    let r=row!(); if r.1.get(0)!=Some(&"VERSION"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=2{return Err((r.0,"BAD_ARITY"));} if r.1[1]!="1"{return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"HMAX"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=2{return Err((r.0,"BAD_ARITY"));} let h=num(r.1[1]).map_err(|e|(r.0,e))?; if !(1..=12).contains(&h){return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"SCAN_RANGE"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=3{return Err((r.0,"BAD_ARITY"));} let slo=num(r.1[1]).map_err(|e|(r.0,e))?; let shi=num(r.1[2]).map_err(|e|(r.0,e))?; if slo<0||slo>=shi||shi>1_000_000{return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"SCALE"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=4{return Err((r.0,"BAD_ARITY"));} let amin=num(r.1[1]).map_err(|e|(r.0,e))?; let amax=num(r.1[2]).map_err(|e|(r.0,e))?; let drift=num(r.1[3]).map_err(|e|(r.0,e))?; if amin<1||amin>amax||amax>1000||amax-amin>30||!(0..=30).contains(&drift){return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"SHIFT"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=3{return Err((r.0,"BAD_ARITY"));} let zmin=num(r.1[1]).map_err(|e|(r.0,e))?; let zmax=num(r.1[2]).map_err(|e|(r.0,e))?; if zmin < -1000||zmin>zmax||zmax>1000||zmax-zmin>20{return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"LIMITS"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=4{return Err((r.0,"BAD_ARITY"));} let mi=num(r.1[1]).map_err(|e|(r.0,e))?; let mm=num(r.1[2]).map_err(|e|(r.0,e))?; let mc=num(r.1[3]).map_err(|e|(r.0,e))?; if [mi,mm,mc].iter().any(|x|!(0..=8).contains(x)){return Err((r.0,"BAD_VALUE"));}
    let r=row!(); if r.1.get(0)!=Some(&"PHASES"){return Err((r.0,"BAD_ORDER"));} if !(2..=4).contains(&r.1.len()){return Err((r.0,"BAD_ARITY"));} let mut phases=Vec::new(); for s in &r.1[1..]{ if s.len()!=1||!matches!(*s,"P"|"I"|"F"){return Err((r.0,"BAD_VALUE"));} let c=s.chars().next().unwrap(); if phases.contains(&c){return Err((r.0,"DUPLICATE"));} phases.push(c); }
    let mut scans=Vec::new(); let mut names=Vec::new(); let mut ids=Vec::new();
    for _ in 0..2 {
        let r=row!(); if r.1.get(0)!=Some(&"SCAN"){return Err((r.0,"BAD_ORDER"));} if r.1.len()!=2{return Err((r.0,"BAD_ARITY"));} if !ident(r.1[1]){return Err((r.0,"BAD_VALUE"));} if names.contains(&r.1[1].to_string()){return Err((r.0,"DUPLICATE"));} names.push(r.1[1].to_string());
        let mut peaks=Vec::new(); let mut last=-1i64;
        loop { let r=row!(); match r.1[0] {
            "END"=>{ if r.1.len()!=1{return Err((r.0,"BAD_ARITY"));} break; },
            "PEAK"=>{ if r.1.len()!=5{return Err((r.0,"BAD_ARITY"));} if !ident(r.1[1]){return Err((r.0,"BAD_VALUE"));} if ids.contains(&r.1[1].to_string()){return Err((r.0,"DUPLICATE"));} let q=num(r.1[2]).map_err(|e|(r.0,e))?; let tol=num(r.1[3]).map_err(|e|(r.0,e))?; let w=num(r.1[4]).map_err(|e|(r.0,e))?; if !(0..=1_000_000).contains(&q)||!(0..=1000).contains(&tol)||!(1..=1000).contains(&w){return Err((r.0,"BAD_VALUE"));} if q<=last{return Err((r.0,"BAD_ORDER"));} if peaks.len()>=8{return Err((r.0,"TOO_MANY_PEAKS"));} last=q; ids.push(r.1[1].to_string()); peaks.push(Peak{id:r.1[1].to_string(),q,tol,weight:w}); },
            _=>return Err((r.0,"UNKNOWN_RECORD")),
        }}
        if peaks.is_empty(){return Err((r.0,"BAD_VALUE"));}
        scans.push(Scan{name:names.last().unwrap().clone(),peaks});
    }
    if p!=rows.len(){return Err((rows[p].0,"BAD_ORDER"));}
    Ok(Study{hmax:h as i32,scan_lo:slo,scan_hi:shi,scale_min:amin,scale_max:amax,drift,shift_min:zmin,shift_max:zmax,max_impurities:mi as usize,max_missing:mm as usize,min_consensus:mc as usize,phases,scans})
}

# ruff: noqa: E401, E701, E702
from pathlib import Path
import json,sys,re
STAGES=['parse','formulas','deps','order','values','errors','recalculation','lineage','audit','metrics','summary']
def cells_range(a,b):
 def rc(x):
  m=re.match(r'([A-Z]+)(\d+)',x); c=0
  for ch in m.group(1): c=c*26+ord(ch)-64
  return int(m.group(2)),c
 def cr(r,c):
  s=''
  while c: c,rem=divmod(c-1,26); s=chr(65+rem)+s
  return s+str(r)
 r1,c1=rc(a); r2,c2=rc(b); return [cr(r,c) for r in range(min(r1,r2),max(r1,r2)+1) for c in range(min(c1,c2),max(c1,c2)+1)]
def solve(path):
 wb=json.loads(Path(path).read_text()); cells={}; formulas={}; names=wb.get('names',{})
 for sh in wb['sheets']:
  for c,v in sh['cells'].items():
   fid=f'{sh["name"]}!{c}'; cells[fid]=v
   if isinstance(v,str) and v.startswith('='): formulas[fid]=v
 pat=re.compile(r'([A-Za-z_][A-Za-z0-9_]*![A-Z]+\d+(?::[A-Z]+\d+)?|[A-Z]+\d+(?::[A-Z]+\d+)?|[A-Za-z_][A-Za-z0-9_]*)'); funcs={'IF','SUM','MIN','MAX','COUNT'}
 def expand(tok,cur):
  tok=names.get(tok,tok); sh=cur; addr=tok
  if '!' in tok: sh,addr=tok.split('!',1)
  return [f'{sh}!{x}' for x in cells_range(*addr.split(':'))] if ':' in addr else [f'{sh}!{addr}']
 deps={}
 for fid,f in formulas.items():
  cur=fid.split('!')[0]; ds=[]
  for t in pat.findall(f[1:]):
   if t.upper() in funcs: continue
   if re.match(r'^[A-Za-z_]',t) and t not in names and not re.search(r'[A-Z]+\d+',t): continue
   ds+=expand(t,cur)
  deps[fid]=sorted(set(ds))
 visiting=set(); done=set(); cycles=set(); order=[]
 def dfs(n,st):
  if n in done: return
  if n in visiting: cycles.update(st[st.index(n):]); return
  visiting.add(n)
  for d in deps.get(n,[]):
   if d in formulas: dfs(d,st+[d])
  visiting.remove(n); done.add(n); order.append(n)
 for n in sorted(formulas): dfs(n,[n])
 order=[x for x in order if x not in cycles]
 def eval_all(base):
  vals={}
  def val(fid):
   if fid in vals: return vals[fid]
   raw=base.get(fid)
   if fid in cycles: vals[fid]='#CYCLE'; return vals[fid]
   if isinstance(raw,(int,float)): vals[fid]=raw; return raw
   if not (isinstance(raw,str) and raw.startswith('=')): vals[fid]=raw; return raw
   try:
    vals[fid]=calc(raw[1:],fid.split('!')[0]); return vals[fid]
   except ZeroDivisionError: vals[fid]='#DIV0'; return vals[fid]
   except Exception: vals[fid]='#VALUE'; return vals[fid]
  def calc(expr,cur):
   while True:
    m=re.search(r'(SUM|MIN|MAX|COUNT)\(([^()]+)\)',expr)
    if not m: break
    vs=[val(x) for x in expand(m.group(2).strip(),cur)]; err=next((x for x in vs if isinstance(x,str) and x.startswith('#')),None)
    rep=err if err else (sum(v for v in vs if isinstance(v,(int,float))) if m.group(1)=='SUM' else min(vs) if m.group(1)=='MIN' else max(vs) if m.group(1)=='MAX' else sum(isinstance(v,(int,float)) for v in vs))
    expr=expr[:m.start()]+str(rep)+expr[m.end():]
   m=re.match(r'IF\((.*),(.*),(.*)\)$',expr)
   if m: expr=m.group(2) if simple(m.group(1),cur) else m.group(3)
   return simple(expr,cur)
  def simple(e,cur):
   for t in sorted(set(pat.findall(e)),key=len,reverse=True):
    if t.upper() in funcs: continue
    if re.match(r'^[A-Za-z_]',t) and t not in names and not re.search(r'[A-Z]+\d+',t): continue
    v=val(expand(t,cur)[0])
    if isinstance(v,str) and v.startswith('#'): return v
    e=e.replace(t,str(v))
   if '/0' in e: raise ZeroDivisionError
   return eval(e,{"__builtins__":{}},{})
  for k in sorted(base): val(k)
  return vals
 cur=dict(cells); final=eval_all(cur); rec=[]
 for ed in wb.get('edits',[]):
  before=final; cur[ed['cell']]=ed['value']
  if isinstance(ed['value'],str) and ed['value'].startswith('='): formulas[ed['cell']]=ed['value']
  final=eval_all(cur); rec.append({'id':ed['id'],'changed':sorted([k for k in final if final.get(k)!=before.get(k)]),'recomputed':sorted(final)})
 errors=[{'cell':k,'error':v} for k,v in sorted(final.items()) if isinstance(v,str) and v.startswith('#')]
 def trans(k):
  seen=set(); st=list(deps.get(k,[]))
  while st:
   x=st.pop()
   if x in seen: continue
   if x in formulas:
    seen.add(x); st+=deps.get(x,[])
  return sorted(seen)
 lineage=[{'cell':k,'direct':deps.get(k,[]),'transitive':trans(k)} for k in sorted(formulas)]
 audit=[]; checksum=0; nsum=0; textc=0
 for k in sorted(formulas):
  v=final.get(k); state='cycle' if v=='#CYCLE' else 'error' if isinstance(v,str) and v.startswith('#') else 'value'
  audit.append({'cell':k,'state':state,'value':v})
  if isinstance(v,(int,float)): nsum+=v
  if isinstance(v,str) and not v.startswith('#'): textc+=1
  for ch in f'{k}={v}': checksum=(checksum*131+ord(ch))%1000000007
 return {'parse':{'sheets':len(wb['sheets']),'cells':len(cells),'formulas':len(formulas),'names':len(names),'edits':len(wb.get('edits',[]))},'formulas':{'formulas':[{'cell':k,'formula':v} for k,v in sorted(formulas.items())]},'deps':{'deps':[{'cell':k,'depends_on':deps.get(k,[])} for k in sorted(formulas)]},'order':{'order':order,'cycles':sorted(cycles)},'values':{'values':{k:final[k] for k in sorted(final)}},'errors':{'errors':errors},'recalculation':{'edits':rec},'lineage':{'lineage':lineage},'audit':{'audit':audit},'metrics':{'max_direct_dependencies':max([len(deps.get(k,[])) for k in formulas] or [0]),'max_transitive_dependencies':max([len(x['transitive']) for x in lineage] or [0]),'numeric_formula_sum':nsum,'text_formula_count':textc,'checksum':checksum},'summary':{'formulas':len(formulas),'dependencies':sum(len(v) for v in deps.values()),'cycles':len(cycles),'errors':len(errors),'edits':len(wb.get('edits',[])),'lineage_edges':sum(len(x['transitive']) for x in lineage)}}
def main():
 out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
 for k,v in solve(sys.argv[1]).items(): (out/f'{k}.json').write_text(json.dumps(v,separators=(',',':'))+'\n')
if __name__=='__main__': main()

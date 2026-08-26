const baseUrl = process.argv[2];
if (!baseUrl) {
  process.stderr.write("usage: node /app/safari_dispatch.mjs <base_url>\n");
  process.exit(2);
}

async function readState() {
  const response = await fetch(`${baseUrl}/state`);
  if (!response.ok) throw new Error(`GET /state failed with ${response.status}`);
  return await response.json();
}

async function advance(payload) {
  const response = await fetch(`${baseUrl}/act`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`POST /act failed with ${response.status}`);
  return await response.json();
}

function makeSolver(){
  const mem = {};
  const PAIRS = {
    north: { assessor:'tracker_ama', observer:'spotter_jo', seq:['habitat_1','habitat_2','habitat_3','habitat_4','habitat_5'] },
    south: { assessor:'ranger_kito', observer:'ornithologist_lei', seq:['habitat_10','habitat_9','habitat_8','habitat_7','habitat_6'] }
  };
  function pathNext(state, from, to){
    if(from===to) return null;
    const hb=new Map(state.habitats.map(h=>[h.id,h]));
    const q=[from]; const par=new Map([[from,null]]);
    while(q.length){const c=q.shift(); if(c===to) break; for(const n of hb.get(c).neighbors){ if(par.has(n))continue; par.set(n,c); q.push(n);} }
    if(!par.has(to)) return null; let cur=to; while(par.get(cur)!==from) cur=par.get(cur); return cur;
  }
  function routeBetween(state,a,b){ const id=[a,b].sort().join('--'); return state.routes.find(r=>r.id===id); }
  function habOf(state,id){ return state.habitats.find(h=>h.id===id); }
  function expOf(state,id){ return state.explorers.find(e=>e.id===id); }
  function bestSighting(hab){
    let hi = hab.sightings.filter(s=>s.quality==='high');
    if(hi.length) return hi[hi.length-1];
    let med = hab.sightings.filter(s=>s.quality==='medium');
    if(med.length) return med[med.length-1];
    return hab.sightings.length? hab.sightings[hab.sightings.length-1]: null;
  }
  function idle(exp, cmds, thresh=5.5){ if(exp.fatigue>thresh) cmds.push({type:'rest',explorer_id:exp.id}); }
  function assessorAction(state,A,hab,P,cmds){
    if(A.location!==hab.id){ idle(A,cmds); return; }
    const idx=P.seq.indexOf(hab.id);
    let nextId=null;
    if(idx>=0 && idx+1<P.seq.length) nextId=P.seq[idx+1];
    if(nextId){
      const id=[hab.id,nextId].sort().join('--');
      const rt=state.routes.find(r=>r.id===id);
      if(rt && !rt.assessed){ cmds.push({type:'assess_route',explorer_id:A.id,to:nextId}); return; }
    }
    idle(A,cmds);
  }
  return function decide(state){
    const finishFloor = state.limits.finish_floor;
    const allReported = state.summary.reports_filed === state.summary.required_reports;
    if(allReported && state.turn >= finishFloor) return {finish:true};
    const cmds=[];
    for(const pk of ['north','south']){
      const P=PAIRS[pk];
      const A=expOf(state,P.assessor); const B=expOf(state,P.observer);
      const loc=B.location;
      const targetHab = P.seq.map(id=>habOf(state,id)).find(h=>!h.reported);
      if(!targetHab){ idle(A,cmds); idle(B,cmds); continue; }
      if(loc===targetHab.id){
        const hab=targetHab;
        const hasHigh = hab.sightings.some(s=>s.quality==='high');
        const cond=state.conditions;
        const blocking=['rain','dust'].includes(cond.weather);
        if(hab.sightings.length===0){
          if(B.fatigue>7){ cmds.push({type:'rest',explorer_id:B.id}); }
          else cmds.push({type:'observe',explorer_id:B.id});
          assessorAction(state,A,hab,P,cmds);
        } else if(!hasHigh){
          const sight=hab.sightings[0];
          const pref=sight.preferred_phase;
          const phaseOk = cond.phase===pref;
          const canHigh = phaseOk && !blocking && B.fatigue<=7 && hab.disturbance<=2;
          if(canHigh){ cmds.push({type:'observe',explorer_id:B.id}); }
          else {
            const key=hab.id+'_wait';
            mem[key]=(mem[key]||0)+1;
            if(mem[key]>10){ const best=bestSighting(hab); cmds.push({type:'report',explorer_id:B.id,species_id:best.species_id,estimate:best.observed_count}); }
            else { idle(B,cmds); }
          }
          assessorAction(state,A,hab,P,cmds);
        } else {
          const best=bestSighting(hab);
          cmds.push({type:'report',explorer_id:B.id,species_id:best.species_id,estimate:best.observed_count});
          assessorAction(state,A,hab,P,cmds);
        }
      } else {
        const nxt=pathNext(state,loc,targetHab.id);
        const rt=routeBetween(state,loc,nxt);
        if(rt && !rt.assessed){
          cmds.push({type:'assess_route',explorer_id:A.id,to:nxt});
          idle(B,cmds);
        } else {
          cmds.push({type:'move',explorer_id:A.id,to:nxt});
          cmds.push({type:'move',explorer_id:B.id,to:nxt});
        }
      }
    }
    return {commands:cmds};
  };
}

const decide = makeSolver();
let state = await readState();
let guard = 0;
while (state.status === "active" && guard < 1000) {
  guard += 1;
  const result = await advance(decide(state));
  state = result;
}

process.stdout.write(`${JSON.stringify({ status: state.status, end_reason: state.end_reason, score: state.score })}\n`);

#!/bin/bash
set -euo pipefail

echo "==> Step 1: Setting up directories..."
mkdir -p /app/backend /app/static /app/data /app/frontend/src/components /app/frontend/src/hooks

echo "==> Step 2: Writing backend..."
cat > /app/backend/__init__.py << 'EOF'
EOF

cat > /app/backend/main.py << 'EOF'
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

TRANSCRIPT_PATH = Path("/app/data/incident_transcript.txt")
STATIC_DIR = Path("/app/static")
CHUNK_SIZE = 250
CHUNK_OVERLAP = 40
BM25_K1 = 1.5
BM25_B = 0.75
IDF_CAP = 2.5  # cap so ultra-rare but tangential terms don't dominate

app = FastAPI(title="RAG Incident Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class Passage(BaseModel):
    id: int
    text: str
    score: float
    citation: str
    highlighted_snippet: str

class QueryResponse(BaseModel):
    question: str
    passages: List[Passage]
    answer: str

STOPWORDS = set([
    "the","a","an","and","or","but","in","on","at","to","for","of","is","it",
    "its","that","this","was","with","be","are","as","by","from","have","has",
    "had","not","we","our","they","their","will","can","been","were","he","she",
    "i","you","my","all","also","more","after","before","about","which","when",
])

def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = []
    for raw in re.findall(r'\b[a-zA-Z0-9_\-\.]+\b', text):
        if len(raw) > 1 and raw not in STOPWORDS:
            tokens.append(raw)
        # Decompose compound identifiers (idx_user_sessions_created_at -> idx, user, sessions, created, at)
        if any(sep in raw for sep in "_-."):
            for sub in re.split(r'[_\-\.]', raw):
                if len(sub) > 1 and sub not in STOPWORDS and sub != raw:
                    tokens.append(sub)
    return tokens

def chunk_text(text: str) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i:i+CHUNK_SIZE]))
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

class BM25Index:
    def __init__(self, chunks):
        self.N = len(chunks)
        self.doc_tfs = []
        self.doc_lens = []
        df = defaultdict(int)
        for chunk in chunks:
            toks = tokenize(chunk)
            self.doc_lens.append(len(toks) or 1)
            tf = defaultdict(int)
            for t in toks:
                tf[t] += 1
            self.doc_tfs.append(dict(tf))
            for t in set(toks):
                df[t] += 1
        self.avg_dl = sum(self.doc_lens) / max(1, self.N)
        self.idf = {
            t: min(IDF_CAP, math.log(1 + (self.N - df[t] + 0.5) / (df[t] + 0.5)))
            for t in df
        }

    def score(self, query_tokens):
        scores = []
        for i, tf in enumerate(self.doc_tfs):
            s = 0.0
            dl = self.doc_lens[i]
            for qt in query_tokens:
                if qt not in tf:
                    continue
                idf = self.idf.get(qt, 0.0)
                f = tf[qt]
                num = f * (BM25_K1 + 1)
                den = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / self.avg_dl)
                s += idf * num / den
            scores.append(s)
        return scores

all_chunks: List[str] = []
bm25: BM25Index = None  # type: ignore
query_history: List[dict] = []

VALIDATION_QUESTIONS = [
    {"question": "What was the root cause of the incident?", "keywords": ["connection pool","exhaustion","user_sessions","query"]},
    {"question": "When did the incident start?", "keywords": ["02:14","2024-03-15","alert"]},
    {"question": "How was the connection pool issue resolved?", "keywords": ["200","pool","connections","increased"]},
    {"question": "What index was created to fix the slow query?", "keywords": ["idx_user_sessions_created_at","created_at","index"]},
    {"question": "What was the financial impact?", "keywords": ["2,484,132","revenue","impact"]},
    {"question": "Which ORM version caused the regression?", "keywords": ["sqlalchemy","1.4","2.0"]},
    {"question": "Who was the incident commander?", "keywords": ["emma.patel","incident commander"]},
    {"question": "What was query execution time before and after fix?", "keywords": ["8423","43","ms"]},
]

@app.on_event("startup")
def startup():
    global all_chunks, bm25
    if TRANSCRIPT_PATH.exists():
        text = TRANSCRIPT_PATH.read_text(encoding="utf-8")
        all_chunks = chunk_text(text)
        bm25 = BM25Index(all_chunks)
        print(f"Indexed {len(all_chunks)} chunks (avg_dl={bm25.avg_dl:.1f})")

@app.get("/health")
def health():
    return {"status": "ok", "chunks_loaded": len(all_chunks)}

def highlight_snippet(text: str, query_tokens: List[str], window: int = 200) -> str:
    """Return a ~window-char excerpt of text with each query token wrapped in <mark>.
    Matching is case-insensitive on word boundaries, skipping stopwords and very short tokens."""
    marks = [t for t in query_tokens if len(t) > 2 and t not in STOPWORDS]
    if not marks:
        return text[:window]
    lowered = text.lower()
    # Center window on the first matched token position, else start at 0
    center = -1
    for m in marks:
        pos = lowered.find(m)
        if pos != -1:
            center = pos
            break
    if center == -1:
        excerpt = text[:window]
    else:
        start = max(0, center - window // 2)
        end = min(len(text), start + window)
        excerpt = text[start:end]
    # Wrap each mark occurrence with <mark>...</mark>, case-insensitive on word boundaries
    def repl(match):
        return f"<mark>{match.group(0)}</mark>"
    for m in marks:
        pattern = re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE)
        excerpt = pattern.sub(repl, excerpt)
    return excerpt

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    if not all_chunks:
        raise HTTPException(status_code=503, detail="not loaded")
    qtoks = tokenize(req.question)
    scores = bm25.score(qtoks)
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
    max_s = max(scores) if scores and max(scores) > 0 else 1.0
    passages = []
    for r, i in enumerate(ranked[:req.top_k]):
        passages.append(Passage(
            id=i,
            text=all_chunks[i],
            score=round(scores[i] / max_s, 4),
            citation=f"[{r+1}]",
            highlighted_snippet=highlight_snippet(all_chunks[i], qtoks),
        ))
    cites = "".join(p.citation for p in passages[:3])
    answer = (
        f"Based on passages {cites}: {passages[0].text[:200]}..."
        if passages else "No results."
    )
    query_history.append({"question": req.question, "answer": answer})
    if len(query_history) > 50:
        query_history.pop(0)
    return QueryResponse(question=req.question, passages=passages, answer=answer)

@app.get("/history")
def get_history():
    return list(reversed(query_history))

@app.get("/passages")
def get_passages():
    return [{"id": i, "preview": c[:200]} for i, c in enumerate(all_chunks)]

@app.get("/validate")
def validate():
    if not all_chunks:
        raise HTTPException(status_code=503, detail="not loaded")
    results = []
    for vq in VALIDATION_QUESTIONS:
        qtoks = tokenize(vq["question"])
        scores = bm25.score(qtoks)
        top5 = sorted(range(len(scores)), key=lambda i: -scores[i])[:5]
        ids = list(top5)
        hit, rr = False, 0.0
        for rank, i in enumerate(top5, 1):
            if any(kw.lower() in all_chunks[i].lower() for kw in vq["keywords"]):
                hit, rr = True, 1.0/rank
                break
        results.append({
            "question": vq["question"],
            "expected_keywords": vq["keywords"],
            "retrieved_passage_ids": ids,
            "hit_at_k": hit,
            "reciprocal_rank": round(rr, 4),
            "top_passage_text": all_chunks[ids[0]][:300] if ids else "",
        })
    mrr = sum(r["reciprocal_rank"] for r in results) / len(results)
    hit_rate = sum(1 for r in results if r["hit_at_k"]) / len(results)
    return {
        "results": results,
        "mrr": round(mrr, 4),
        "hit_rate": round(hit_rate, 4),
        "n_questions": len(results),
    }

@app.get("/assets/{path:path}")
def serve_asset(path: str):
    asset_file = STATIC_DIR / "assets" / path
    if asset_file.exists() and asset_file.is_file():
        return FileResponse(str(asset_file))
    raise HTTPException(status_code=404, detail="Asset not found")

@app.get("/")
def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"message": "frontend not built"}

@app.get("/{path:path}")
def catchall(path: str):
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    raise HTTPException(status_code=404)
EOF

echo "==> Step 3: Writing React frontend..."
cat > /app/frontend/src/App.jsx << 'EOF'
import React, { useState, useCallback } from 'react'
import QueryPanel from './components/QueryPanel'
import ResultsPanel from './components/ResultsPanel'
import ValidationPanel from './components/ValidationPanel'

export default function App() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('query')

  const handleQuery = useCallback(async (question, topK) => {
    setLoading(true); setError(null); setResults(null)
    const startTime = Date.now()
    const MIN_LOADING_MS = 300
    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({question, top_k: topK}),
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      setResults(await res.json())
    } catch(e) { setError(e.message) }
    finally {
      const elapsed = Date.now() - startTime
      if (elapsed < MIN_LOADING_MS) {
        await new Promise(r => setTimeout(r, MIN_LOADING_MS - elapsed))
      }
      setLoading(false)
    }
  }, [])

  return (
    <div style={{maxWidth:1100,margin:'0 auto',padding:'24px 16px',fontFamily:'system-ui',background:'#0f172a',color:'#e2e8f0',minHeight:'100vh'}}>
      <h1 style={{fontSize:24,fontWeight:700,marginBottom:4}}>RAG Incident Dashboard</h1>
      <p style={{color:'#94a3b8',fontSize:14,marginBottom:20}}>Retrieval-augmented analysis of INC-2024-0847</p>
      <nav style={{display:'flex',gap:8,marginBottom:20}}>
        {['query','validate'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{padding:'8px 20px',borderRadius:8,border:'none',cursor:'pointer',fontWeight:600,fontSize:14,background:tab===t?'#3b82f6':'#1e293b',color:tab===t?'#fff':'#94a3b8'}}>
            {t==='query'?'Query':'Validate'}
          </button>
        ))}
      </nav>
      {tab==='query' && <>
        <QueryPanel onQuery={handleQuery} loading={loading}/>
        <div data-testid="loading-indicator" style={{textAlign:'center',padding:32,color:'#94a3b8',display:loading?'block':'none'}}>Retrieving...</div>
        {error && <div style={{background:'#450a0a',borderRadius:8,padding:16,color:'#fca5a5'}}>{error}</div>}
        {results && !loading && <ResultsPanel results={results}/>}
      </>}
      {tab==='validate' && <ValidationPanel/>}
    </div>
  )
}
EOF

cat > /app/frontend/src/components/QueryPanel.jsx << 'EOF'
import React, { useState } from 'react'
export default function QueryPanel({ onQuery, loading }) {
  const [q, setQ] = useState('')
  const [k, setK] = useState(5)
  const submit = () => q.trim() && onQuery(q.trim(), k)
  return (
    <div style={{background:'#1e293b',borderRadius:12,padding:20,marginBottom:20,border:'1px solid #334155'}}>
      <div style={{display:'flex',gap:10,marginBottom:10}}>
        <input data-testid="question-input" value={q} onChange={e=>setQ(e.target.value)}
          onKeyDown={e=>e.key==='Enter'&&submit()}
          placeholder="Ask a question about the incident..."
          style={{flex:1,padding:'10px 14px',borderRadius:8,border:'1px solid #334155',background:'#0f172a',color:'#e2e8f0',fontSize:14,outline:'none'}}/>
        <button data-testid="submit-btn" onClick={submit} disabled={loading||!q.trim()}
          style={{padding:'10px 24px',borderRadius:8,border:'none',background:loading||!q.trim()?'#334155':'#3b82f6',color:'#fff',fontWeight:600,cursor:loading||!q.trim()?'not-allowed':'pointer'}}>
          {loading?'Searching...':'Search'}
        </button>
      </div>
    </div>
  )
}
EOF

cat > /app/frontend/src/components/ResultsPanel.jsx << 'EOF'
import React from 'react'
export default function ResultsPanel({ results }) {
  return (
    <div>
      <div style={{background:'#1e293b',borderRadius:12,padding:16,border:'1px solid #334155',marginBottom:16}}>
        <p style={{fontSize:14,color:'#e2e8f0'}}>{results.answer}</p>
      </div>
      <div data-testid="results-area">
        {results.passages.map(p => (
          <div key={p.id} data-testid="passage-card" style={{background:'#1e293b',borderRadius:10,padding:16,border:'1px solid #334155',marginBottom:10}}>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
              <span style={{background:'#1d4ed8',color:'#bfdbfe',padding:'2px 10px',borderRadius:4,fontSize:13,fontWeight:700}}>{p.citation}</span>
              <span data-testid="confidence-score" style={{fontSize:13,fontWeight:600,color:'#22c55e'}}>{Math.round(p.score*100)}%</span>
            </div>
            <p style={{fontSize:13,color:'#cbd5e1',lineHeight:1.7}}>{p.text.slice(0,400)}{p.text.length>400?'...':''}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
EOF

cat > /app/frontend/src/components/ValidationPanel.jsx << 'EOF'
import React, { useState } from 'react'
export default function ValidationPanel() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const run = async () => {
    setLoading(true)
    try { setData(await (await fetch('/validate')).json()) }
    finally { setLoading(false) }
  }
  return (
    <div data-testid="validation-panel">
      <div style={{background:'#1e293b',borderRadius:12,padding:20,marginBottom:16,border:'1px solid #334155'}}>
        <h2 style={{fontSize:18,fontWeight:700,marginBottom:8}}>Model Evaluation</h2>
        <button onClick={run} disabled={loading}
          style={{padding:'8px 24px',borderRadius:8,border:'none',background:loading?'#334155':'#7c3aed',color:'#fff',fontWeight:600,cursor:loading?'not-allowed':'pointer'}}>
          {loading?'Running...':'Run Evaluation'}
        </button>
      </div>
      {data && (
        <>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12,marginBottom:16}}>
            {[['MRR',data.mrr.toFixed(3),'#22c55e'],['Hit Rate',`${(data.hit_rate*100).toFixed(1)}%`,'#3b82f6'],['Questions',data.n_questions,'#f59e0b']].map(([l,v,c]) => (
              <div key={l} style={{background:'#1e293b',borderRadius:10,padding:16,textAlign:'center',border:'1px solid #334155'}}>
                <div style={{fontSize:28,fontWeight:700,color:c}}>{v}</div>
                <div style={{fontSize:12,color:'#94a3b8'}}>{l}</div>
              </div>
            ))}
          </div>
          {data.results.map((r,i) => (
            <div key={i} style={{background:'#1e293b',borderRadius:10,padding:14,marginBottom:8,border:`1px solid ${r.hit_at_k?'#166534':'#7f1d1d'}`}}>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                <span style={{fontSize:14,color:'#e2e8f0'}}>{r.question}</span>
                <span style={{fontSize:12,padding:'2px 8px',borderRadius:4,background:r.hit_at_k?'#14532d':'#450a0a',color:r.hit_at_k?'#86efac':'#fca5a5'}}>{r.hit_at_k?'Hit':'Miss'}</span>
              </div>
              <p style={{fontSize:12,color:'#64748b'}}>{r.top_passage_text?.slice(0,200)}...</p>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
EOF

cat > /app/frontend/src/main.jsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
EOF

cat > /app/frontend/src/index.css << 'EOF'
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0}
EOF

echo "==> Step 4: Building React frontend..."
cd /app/frontend
if [ -d /opt/frontend-deps/node_modules ]; then
    ln -sf /opt/frontend-deps/node_modules ./node_modules
else
    npm install
fi
npm run build
cd /app

echo "==> Step 5: Starting FastAPI backend as background daemon..."
cd /app
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
API_PID=$!

echo "==> Waiting for API..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "==> API is up!"
        break
    fi
    sleep 1
done

curl -sf http://localhost:8000/health || echo "Warning: API did not start"
echo ""
echo "==> Solution complete!"

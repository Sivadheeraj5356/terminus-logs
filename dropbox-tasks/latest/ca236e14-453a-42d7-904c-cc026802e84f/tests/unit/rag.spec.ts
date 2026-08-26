import { describe, it, expect } from "vitest";

const API_BASE = "http://localhost:8000";

describe("RAG API — live server", () => {
  it("GET /health returns ok with chunks loaded", async () => {
    const res = await fetch(`${API_BASE}/health`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.status).toBe("ok");
    expect(data.chunks_loaded).toBeGreaterThan(0);
  });

  it("POST /query returns valid passage array with required fields", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "root cause of the incident", top_k: 3 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(Array.isArray(data.passages)).toBe(true);
    expect(data.passages.length).toBeGreaterThan(0);
    expect(typeof data.passages[0].id).toBe("number");
    expect(typeof data.passages[0].text).toBe("string");
    expect(typeof data.passages[0].score).toBe("number");
    expect(data.passages[0].citation).toMatch(/^\[\d+\]$/);
    expect(data.answer).toBeTruthy();
  });

  it("GET /passages returns chunk list with id and preview", async () => {
    const res = await fetch(`${API_BASE}/passages`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    expect(typeof data[0].id).toBe("number");
    expect(typeof data[0].preview).toBe("string");
  });

  it("GET /validate returns mrr and hit_rate with results", async () => {
    const res = await fetch(`${API_BASE}/validate`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(typeof data.mrr).toBe("number");
    expect(typeof data.hit_rate).toBe("number");
    expect(data.results.length).toBeGreaterThanOrEqual(5);
  });

  it("POST /query returns 400 for empty question", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "", top_k: 5 }),
    });
    expect(res.status).toBe(400);
  });

  it("retrieval is query-dependent: different queries return different top passages", async () => {
    const r1 = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "connection pool exhaustion database slowdown", top_k: 3 }),
    });
    const r2 = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "packet loss network region AWS availability zone", top_k: 3 }),
    });
    const d1 = await r1.json();
    const d2 = await r2.json();
    const ids1 = d1.passages.map((p: any) => p.id);
    const ids2 = d2.passages.map((p: any) => p.id);
    expect(ids1).not.toEqual(ids2);
  });

  it("retrieval is deterministic: same query returns same top passage", async () => {
    const q = { question: "What was the root cause of the incident?", top_k: 3 };
    const r1 = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(q),
    });
    const r2 = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(q),
    });
    const d1 = await r1.json();
    const d2 = await r2.json();
    expect(d1.passages[0].id).toBe(d2.passages[0].id);
    expect(d1.passages[0].score).toBe(d2.passages[0].score);
  });

  it("verifier keyword check: root cause query returns connection-pool-related passage", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What caused the connection pool to exhaust?", top_k: 5 }),
    });
    const data = await res.json();
    const allText = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
    expect(
      allText.includes("connection pool") || allText.includes("exhaustion") || allText.includes("user_sessions")
    ).toBe(true);
  });

  it("verifier keyword check: replication lag query returns replication-related passage", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "When did replication lag exceed 60 seconds?", top_k: 5 }),
    });
    const data = await res.json();
    const allText = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
    expect(allText.includes("replication") || allText.includes("lag")).toBe(true);
  });

  it("answer field includes inline passage citation in [N] format", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What was the root cause of the incident?", top_k: 3 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    // The synthesised answer must reference multiple retrieved passages
    // using the same [N] citation labels that appear on the passage cards —
    // at least two distinct citations so users can trace the response back
    // to more than one source of evidence.
    const citations = data.answer.match(/\[\d+\]/g) ?? [];
    const distinctCitations = new Set(citations);
    expect(distinctCitations.size).toBeGreaterThanOrEqual(2);
  });

  it("each passage exposes a highlighted_snippet with query terms wrapped in <mark> tags", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "connection pool exhaustion database", top_k: 3 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.passages.length).toBeGreaterThan(0);
    for (const p of data.passages) {
      // Field must be a string containing at least one <mark>...</mark> wrapper
      expect(typeof p.highlighted_snippet).toBe("string");
      expect(p.highlighted_snippet.length).toBeGreaterThan(0);
      const markMatches = p.highlighted_snippet.match(/<mark>[^<]+<\/mark>/gi) ?? [];
      expect(markMatches.length).toBeGreaterThanOrEqual(1);
      // The wrapped content must correspond to a query term, case-insensitive.
      const queryTerms = ["connection", "pool", "exhaustion", "database"];
      const marked = markMatches
        .map(m => m.replace(/<\/?mark>/gi, "").toLowerCase());
      const matchesQueryTerm = marked.some(m =>
        queryTerms.some(q => m.includes(q) || q.includes(m))
      );
      expect(matchesQueryTerm).toBe(true);
    }
  });

  it("passages are returned sorted by relevance score descending", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "connection pool exhaustion root cause database", top_k: 5 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.passages.length).toBeGreaterThan(1);
    for (let i = 0; i < data.passages.length - 1; i++) {
      expect(data.passages[i].score).toBeGreaterThanOrEqual(data.passages[i + 1].score);
    }
  });

  it("GET /history records queries submitted via POST /query", async () => {
    const question = "What was the financial impact of the outage?";
    await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 3 }),
    });
    const res = await fetch(`${API_BASE}/history`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
    // Most recent query should appear in history
    const item = data.find((h: any) => h.question === question);
    expect(item).toBeDefined();
    expect(typeof item.answer).toBe("string");
    expect(item.answer.length).toBeGreaterThan(0);
  });

  it("verifier retrieval: database-index query must surface idx_user_sessions passage", async () => {
    // Verifier-controlled query — not gameable via validation_questions.py
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "Which database index caused the query performance degradation?", top_k: 3 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    const top3 = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
    expect(top3).toMatch(/idx_user_sessions|user_sessions_created_at/);
  });

  it("verifier retrieval: financial impact query surfaces multiple revenue-related terms", async () => {
    const res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What was the total financial impact and revenue loss from the outage?", top_k: 3 }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    const top3 = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
    // A correct TF-IDF implementation must rank revenue/financial passages in top-3
    const hits = ["revenue", "financial", "million", "cost"].filter(k => top3.includes(k));
    expect(hits.length).toBeGreaterThanOrEqual(2);
  });

  it("chunks are overlapping: consecutive passages share boundary words", async () => {
    const res = await fetch(`${API_BASE}/passages`);
    expect(res.ok).toBe(true);
    const passages = await res.json();
    expect(passages.length).toBeGreaterThanOrEqual(150);
    let overlappingPairs = 0;
    const N = Math.min(passages.length - 1, 40);
    for (let i = 0; i < N; i++) {
      const curr = String(passages[i].preview || "").toLowerCase();
      const next = String(passages[i + 1].preview || "").toLowerCase();
      const tailWords = new Set(curr.split(/\s+/).filter((w: string) => w.length > 4).slice(-25));
      const headWords = next.split(/\s+/).filter((w: string) => w.length > 4).slice(0, 35);
      if (headWords.some((w: string) => tailWords.has(w))) overlappingPairs++;
    }
    // With CHUNK_OVERLAP > 0, most consecutive pairs must share boundary words
    expect(overlappingPairs).toBeGreaterThan(15);
  });

});

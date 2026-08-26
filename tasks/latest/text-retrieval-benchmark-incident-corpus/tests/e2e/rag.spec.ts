import { test, expect } from "@playwright/test";

const API_BASE = "http://localhost:8000";

// ── Page Load Tests ───────────────────────────────────────────────────────────

test("home page loads and shows dashboard title", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1")).toContainText("RAG Incident Dashboard");
});

test("page has correct title", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("RAG Incident Dashboard");
});

// ── UI Element Tests ──────────────────────────────────────────────────────────

test("question input is present and interactive", async ({ page }) => {
  await page.goto("/");
  const input = page.locator('[data-testid="question-input"]');
  await expect(input).toBeVisible();
  await input.fill("What was the root cause of the incident?");
  await expect(input).toHaveValue("What was the root cause of the incident?");
});

test("submit button is present and visible", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="submit-btn"]')).toBeVisible();
});

test("validation panel is accessible via navigation", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Validate").click();
  await expect(page.locator('[data-testid="validation-panel"]')).toBeVisible();
});

// ── Query Flow Tests ──────────────────────────────────────────────────────────

test("submitting a question shows results area", async ({ page }) => {
  await page.goto("/");
  await page.locator('[data-testid="question-input"]').fill("What was the root cause?");
  await page.locator('[data-testid="submit-btn"]').click();
  await expect(page.locator('[data-testid="results-area"]')).toBeVisible({ timeout: 15000 });
});

test("results show passage cards with citations", async ({ page }) => {
  await page.goto("/");
  await page.locator('[data-testid="question-input"]').fill("What was the root cause of the incident?");
  await page.locator('[data-testid="submit-btn"]').click();
  await page.locator('[data-testid="results-area"]').waitFor({ timeout: 15000 });
  const cards = page.locator('[data-testid="passage-card"]');
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThan(0);
});

test("passage cards show confidence scores", async ({ page }) => {
  await page.goto("/");
  await page.locator('[data-testid="question-input"]').fill("connection pool exhaustion");
  await page.locator('[data-testid="submit-btn"]').click();
  await page.locator('[data-testid="results-area"]').waitFor({ timeout: 15000 });
  await expect(page.locator('[data-testid="confidence-score"]').first()).toBeVisible();
});

test("citation labels are rendered in [N] format", async ({ page }) => {
  await page.goto("/");
  await page.locator('[data-testid="question-input"]').fill("What was the root cause?");
  await page.locator('[data-testid="submit-btn"]').click();
  await page.locator('[data-testid="passage-card"]').first().waitFor({ timeout: 15000 });
  const text = await page.locator('[data-testid="passage-card"]').first().textContent();
  expect(text).toMatch(/\[\d+\]/);
});

// ── Determinism Tests ─────────────────────────────────────────────────────────

test("same query returns same top passage deterministically", async ({ page }) => {
  await page.goto("/");
  const question = "What was the root cause of the incident?";

  await page.locator('[data-testid="question-input"]').fill(question);
  await page.locator('[data-testid="submit-btn"]').click();
  await page.locator('[data-testid="passage-card"]').first().waitFor({ timeout: 15000 });
  const text1 = await page.locator('[data-testid="passage-card"]').first().textContent();

  await page.locator('[data-testid="question-input"]').fill("");
  await page.locator('[data-testid="question-input"]').fill(question);
  await page.locator('[data-testid="submit-btn"]').click();
  await page.locator('[data-testid="passage-card"]').first().waitFor({ timeout: 15000 });
  const text2 = await page.locator('[data-testid="passage-card"]').first().textContent();

  expect(text1).toBe(text2);
});

// ── API Integration Tests ─────────────────────────────────────────────────────

test("API health endpoint returns ok", async ({ request }) => {
  const res = await request.get(`${API_BASE}/health`);
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.status).toBe("ok");
  expect(typeof data.chunks_loaded).toBe("number");
  expect(data.chunks_loaded).toBeGreaterThanOrEqual(150);
});

test("API /query returns passages with citations and scores", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "What was the root cause?", top_k: 5 },
  });
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.question).toBeTruthy();
  expect(Array.isArray(data.passages)).toBe(true);
  expect(data.passages.length).toBeGreaterThan(0);
  const p = data.passages[0];
  expect(typeof p.id).toBe("number");
  expect(typeof p.text).toBe("string");
  expect(typeof p.score).toBe("number");
  expect(p.score).toBeGreaterThanOrEqual(0);
  expect(p.score).toBeLessThanOrEqual(1);
  expect(p.citation).toMatch(/^\[\d+\]$/);
  expect(data.answer).toBeTruthy();
});

test("API /query respects top_k parameter", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "incident", top_k: 3 },
  });
  const data = await res.json();
  expect(data.passages.length).toBeLessThanOrEqual(3);
});

test("API /query returns 400 for empty question", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "", top_k: 5 },
  });
  expect(res.status()).toBe(400);
});

test("API /passages returns list of chunk previews", async ({ request }) => {
  const res = await request.get(`${API_BASE}/passages`);
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(Array.isArray(data)).toBe(true);
  expect(data.length).toBeGreaterThan(0);
  expect(typeof data[0].id).toBe("number");
  expect(typeof data[0].preview).toBe("string");
});

test("API /validate returns MRR and hit_rate metrics", async ({ request }) => {
  const res = await request.get(`${API_BASE}/validate`);
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(typeof data.mrr).toBe("number");
  expect(data.mrr).toBeGreaterThan(0.7);
  expect(data.mrr).toBeLessThanOrEqual(1);
  expect(typeof data.hit_rate).toBe("number");
  expect(data.hit_rate).toBeGreaterThan(0);
  expect(data.hit_rate).toBeLessThanOrEqual(1);
  expect(Array.isArray(data.results)).toBe(true);
  expect(data.results.length).toBeGreaterThanOrEqual(5);
  expect(data.n_questions).toBeGreaterThanOrEqual(5);
});

test("API /validate results contain required fields", async ({ request }) => {
  const res = await request.get(`${API_BASE}/validate`);
  const data = await res.json();
  const r = data.results[0];
  expect(typeof r.question).toBe("string");
  expect(typeof r.hit_at_k).toBe("boolean");
  expect(typeof r.reciprocal_rank).toBe("number");
  expect(Array.isArray(r.retrieved_passage_ids)).toBe(true);
});

test("API retrieval is deterministic across multiple calls", async ({ request }) => {
  const q = { question: "What was the root cause of the incident?", top_k: 3 };
  const res1 = await request.post(`${API_BASE}/query`, { data: q });
  const res2 = await request.post(`${API_BASE}/query`, { data: q });
  const d1 = await res1.json();
  const d2 = await res2.json();
  expect(d1.passages[0].id).toBe(d2.passages[0].id);
  expect(d1.passages[0].score).toBe(d2.passages[0].score);
});

// ── Query-Dependent Retrieval Tests (core RAG behavior) ───────────────────────

test("different queries return different top passages", async ({ request }) => {
  const r1 = await request.post(`${API_BASE}/query`, {
    data: { question: "What was the root cause of the incident?", top_k: 3 },
  });
  const r2 = await request.post(`${API_BASE}/query`, {
    data: { question: "Which regions were affected by packet loss?", top_k: 3 },
  });
  const d1 = await r1.json();
  const d2 = await r2.json();
  const ids1 = d1.passages.map((p: any) => p.id);
  const ids2 = d2.passages.map((p: any) => p.id);
  expect(ids1).not.toEqual(ids2);
});

// ── Verifier-Defined Keyword Tests ────────────────────────────────────────────

test("verifier: connection pool query returns relevant passage", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "What caused the connection pool to exhaust?", top_k: 5 },
  });
  const data = await res.json();
  const allText = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
  expect(
    allText.includes("connection pool") || allText.includes("exhaustion") || allText.includes("user_sessions")
  ).toBe(true);
});

test("verifier: replication lag query returns replication-related passage", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "When did replication lag exceed 60 seconds?", top_k: 5 },
  });
  const data = await res.json();
  const allText = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
  expect(allText.includes("replication") || allText.includes("lag")).toBe(true);
});

test("verifier: financial impact query returns revenue-related passage", async ({ request }) => {
  const res = await request.post(`${API_BASE}/query`, {
    data: { question: "What was the financial impact of the outage?", top_k: 5 },
  });
  const data = await res.json();
  const allText = data.passages.map((p: any) => p.text.toLowerCase()).join(" ");
  expect(["revenue", "impact", "financial"].filter(k => allText.includes(k)).length >= 2).toBe(true);
});

// ── Validation Panel E2E Tests ────────────────────────────────────────────────

test("validation panel runs evaluation and shows metrics", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Validate").click();
  await page.locator('[data-testid="validation-panel"]').waitFor();
  await page.getByRole("button", { name: "Run Evaluation" }).click();
  await expect(page.getByText(/MRR|Hit Rate/i).first()).toBeVisible({ timeout: 20000 });
});

// ── Loading Indicator State Test ─────────────────────────────────────────────

test("loading indicator shows during query and hides after results load", async ({ page }) => {
  await page.goto("/");
  // Not visible before any query
  await expect(page.locator('[data-testid="loading-indicator"]')).not.toBeVisible();
  await page.locator('[data-testid="question-input"]').fill("What was the root cause of the incident?");
  await page.locator('[data-testid="submit-btn"]').click();
  // Must become visible while the query is in-flight
  await expect(page.locator('[data-testid="loading-indicator"]')).toBeVisible({ timeout: 5000 });
  // Must disappear once results arrive
  await expect(page.locator('[data-testid="results-area"]')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('[data-testid="loading-indicator"]')).not.toBeVisible();
});

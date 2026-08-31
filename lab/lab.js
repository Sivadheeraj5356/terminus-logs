(() => {
  const corpus = window.AW_CORPUS;

  if (!corpus || !Array.isArray(corpus.tasks)) {
    const empty = document.getElementById("panel-empty");
    if (empty) {
      empty.textContent =
        "Could not load the lab corpus. Serve this folder over HTTP or keep corpus.js next to index.html.";
    }
    return;
  }

  const CATEGORY_LABELS = {
    "scientific-computing": "Scientific computing",
    security: "Security",
    "system-administration": "System administration",
    "build-and-dependency-management": "Build",
    "data-processing": "Data processing",
    "machine-learning": "Machine learning",
    games: "Games",
    debugging: "Debugging",
  };

  const SUBCATEGORY_LABELS = {
    tool_specific: "Tool-specific",
    db_interaction: "Database",
    api_integration: "API",
    long_context: "Long context",
    ui_building: "UI",
  };

  const PUBLIC_SURFACES = ["overview", "tasks", "challenges"];
  const LAB_SURFACES = ["models", "batches", "harness", "runs", "traces", "failures", "verifier", "agents"];
  const BLOCKED_SURFACES = ["spend", "stump"];
  const SURFACES = [...PUBLIC_SURFACES, ...LAB_SURFACES, "unavailable"];

  const SURFACE_ALIASES = {
    overview: "overview",
    worlds: "overview",
    tasks: "tasks",
    corpus: "tasks",
    catalog: "tasks",
    challenges: "challenges",
    coverage: "challenges",
    models: "models",
    matrix: "models",
    runs: "runs",
    traces: "traces",
    stump: "unavailable",
    failures: "failures",
    verifier: "verifier",
    harness: "harness",
    spend: "unavailable",
    batches: "batches",
    agents: "agents",
    unavailable: "unavailable",
  };

  const FEATURED_MODELS = [
    {
      key: "opus",
      label: "Opus 5",
      slug: "anthropic/claude-opus-5",
      tone: "cell-opus",
      short: "Opus",
      match: (name) => /claude-opus-5|\bopus-5\b/i.test(name),
    },
    {
      key: "gpt56",
      label: "GPT-5.6-sol",
      slug: "openai/gpt-5.6-sol",
      tone: "cell-gpt",
      short: "gpt-5.6-sol",
      match: (name) => /gpt-5\.6-sol/i.test(name),
    },
    {
      key: "grok",
      label: "Grok 4.6",
      slug: "grok-4.6",
      placeholder: true,
      note: "eval queued — no credits",
    },
    {
      key: "glm",
      label: "GLM",
      slug: "glm",
      placeholder: true,
      note: "eval queued — no credits",
    },
    {
      key: "kimi",
      label: "Kimi",
      slug: "kimi",
      placeholder: true,
      note: "eval queued — no credits",
    },
  ];

  const QUEUED_LABEL = "eval queued — no credits";
  const PLANNED = Number((corpus.lab.harness || {}).planned_attempts) || 5;
  const tasks = corpus.tasks;
  const bySlug = new Map(tasks.map((task) => [task.slug, task]));

  const rowsEl = document.getElementById("rows");
  const cardsEl = document.getElementById("catalog-cards");
  const shownEl = document.getElementById("shown");
  const qEl = document.getElementById("q");
  const panelTitle = document.getElementById("panel-title");
  const panelEmpty = document.getElementById("panel-empty");
  const panelBody = document.getElementById("panel-body");

  let category = params().get("filter") || "all";
  let langFilter = params().get("lang") || "all";
  let query = "";
  let catalogView = params().get("view") === "cards" ? "cards" : "table";

  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value;
  }

  function subcategoryLabel(value) {
    return SUBCATEGORY_LABELS[value] || value;
  }

  function languages(task) {
    return task.languages || [];
  }

  function subcategories(task) {
    return task.subcategories || [];
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function params() {
    return new URLSearchParams(window.location.search);
  }

  function currentSlug() {
    return params().get("task") || "";
  }

  function requestedSurface() {
    return (params().get("surface") || "").toLowerCase();
  }

  function isBlockedSurface(id) {
    return BLOCKED_SURFACES.includes(id);
  }

  function currentSurface() {
    const raw = requestedSurface();
    if (isBlockedSurface(raw) || isBlockedSurface(SURFACE_ALIASES[raw])) return "unavailable";
    if (raw && SURFACE_ALIASES[raw]) return SURFACE_ALIASES[raw];
    if (currentSlug()) return "tasks";
    const filter = (params().get("filter") || "").toLowerCase();
    if (filter && filter !== "all") return "tasks";
    return "overview";
  }

  function setUrl({ slug, surface, filter, lang, view, push }) {
    const url = new URL(window.location.href);
    const nextSlug = slug === undefined ? currentSlug() : slug;
    let nextSurface = surface === undefined ? currentSurface() : surface;
    if (isBlockedSurface(nextSurface) || nextSurface === "unavailable") nextSurface = "overview";
    const nextFilter = filter === undefined ? category : filter;
    const nextLang = lang === undefined ? langFilter : lang;
    const nextView = view === undefined ? catalogView : view;
    if (nextSlug) url.searchParams.set("task", nextSlug);
    else url.searchParams.delete("task");
    if (nextSurface && nextSurface !== "overview") url.searchParams.set("surface", nextSurface);
    else url.searchParams.delete("surface");
    if (nextFilter && nextFilter !== "all") url.searchParams.set("filter", nextFilter);
    else url.searchParams.delete("filter");
    if (nextLang && nextLang !== "all") url.searchParams.set("lang", nextLang);
    else url.searchParams.delete("lang");
    if (nextView && nextView !== "table") url.searchParams.set("view", nextView);
    else url.searchParams.delete("view");
    url.searchParams.delete("internal");
    history[push ? "pushState" : "replaceState"](
      { task: nextSlug, surface: nextSurface, filter: nextFilter, lang: nextLang },
      "",
      url
    );
  }

  function isOracleModel(name) {
    const value = String(name || "").toLowerCase();
    return !value || value === "oracle" || value.includes("oracle");
  }

  function agentModels(task) {
    return ((task.rollouts && task.rollouts.by_model) || []).filter((row) => !isOracleModel(row.model));
  }

  function oracleModels(task) {
    return ((task.rollouts && task.rollouts.by_model) || []).filter((row) => isOracleModel(row.model));
  }

  function hasJobs(task) {
    return Boolean(task.measured) || (task.rollouts && task.rollouts.status === "measured");
  }

  function hasAgentJobs(task) {
    return agentModels(task).some((row) => (row.n || 0) > 0);
  }

  function batchNum(task) {
    const n = Number(task && task.batch);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  function batchLabel(n) {
    return String(n).padStart(2, "0");
  }

  function shortModel(name) {
    const raw = String(name || "");
    if (/opus/i.test(raw)) return "Opus 5";
    if (/gpt-5\.6-sol/i.test(raw) || /gpt-5\.6/i.test(raw)) return "GPT-5.6-sol";
    if (/haiku/i.test(raw)) return "claude-haiku-4-5";
    if (/gpt-4o-mini/i.test(raw)) return "gpt-4o-mini";
    if (/sonnet/i.test(raw)) return raw.replace(/^anthropic\//, "");
    return raw.replace(/^anthropic\//, "").replace(/^openai\//, "");
  }

  function recordedN(row) {
    const n = Number(row && row.n);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  function parseBatchFilter(key) {
    if (!key) return 0;
    const m = String(key).toLowerCase().match(/^(?:b|batch)?0*([1-5])$/);
    return m ? Number(m[1]) : 0;
  }

  function normalizeLang(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const lower = raw.toLowerCase();
    const map = {
      go: "Go",
      golang: "Go",
      rust: "Rust",
      rs: "Rust",
      c: "C",
      "c++": "C++",
      cpp: "C++",
      python: "Python",
      py: "Python",
      bash: "Bash",
      sh: "Bash",
      shell: "Bash",
      java: "Java",
      javascript: "JavaScript",
      js: "JavaScript",
      typescript: "TypeScript",
      ts: "TypeScript",
      awk: "Awk",
      minizinc: "MiniZinc",
      r: "R",
      haskell: "Haskell",
      php: "PHP",
      lua: "Lua",
      sql: "SQL",
    };
    return map[lower] || raw;
  }

  function languageSet(task) {
    return languages(task).map(normalizeLang).filter(Boolean);
  }

  function matchesFilter(task) {
    if (!task) return false;
    const batchKey = parseBatchFilter(category);
    if (category === "batch" && batchNum(task) !== 1) return false;
    if (category === "frozen" && !batchNum(task)) return false;
    if (batchKey && batchNum(task) !== batchKey) return false;
    if (category === "measured" && !hasJobs(task)) return false;
    if (category === "agents" && !hasAgentJobs(task)) return false;
    if (
      category !== "all" &&
      category !== "batch" &&
      category !== "frozen" &&
      category !== "measured" &&
      category !== "agents" &&
      !batchKey &&
      task.category !== category
    ) {
      return false;
    }
    if (langFilter && langFilter !== "all") {
      const want = normalizeLang(langFilter).toLowerCase();
      if (!languageSet(task).some((lang) => lang.toLowerCase() === want)) return false;
    }
    return true;
  }

  function matches(task) {
    if (!matchesFilter(task)) return false;
    if (!query) return true;
    const hay = [
      task.name,
      task.slug,
      task.category,
      categoryLabel(task.category),
      languages(task).join(" "),
      subcategories(task).join(" "),
      subcategories(task).map(subcategoryLabel).join(" "),
    ]
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function applyTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute("content", next === "dark" ? "#181B16" : "#FCFAF3");
    try {
      localStorage.setItem("aw-lab-theme", next);
    } catch (_) {
      /* ignore */
    }
  }

  function initTheme() {
    let stored = "";
    try {
      stored = localStorage.getItem("aw-lab-theme") || "";
    } catch (_) {
      stored = "";
    }
    applyTheme(stored === "dark" ? "dark" : "light");
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const now = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(now);
      });
    }
  }

  function renderNav() {
    const active = currentSurface();
    document.body.classList.remove("lab-mode");
    const labNav = document.getElementById("nav-lab");
    if (labNav) labNav.hidden = true;
    document.querySelectorAll("[data-nav]").forEach((el) => {
      const id = SURFACE_ALIASES[el.getAttribute("data-nav")] || el.getAttribute("data-nav");
      if (el.tagName === "BUTTON" || el.tagName === "A") {
        el.setAttribute("aria-current", id === active ? "page" : "false");
      }
    });
  }

  function showSurface(id) {
    SURFACES.forEach((sid) => {
      const el = document.getElementById(`surface-${sid}`);
      if (el) el.hidden = sid !== id;
    });
  }

  function featuredRow(task, spec) {
    if (!spec || spec.placeholder) return null;
    return agentModels(task).find((row) => spec.match(row.model || "") && recordedN(row) > 0) || null;
  }

  function queuedCell() {
    return `<span class="cell-queued">${QUEUED_LABEL}</span>`;
  }

  function modelCell(task, spec) {
    if (!spec || spec.placeholder) return queuedCell();
    const row = featuredRow(task, spec);
    if (!row) return queuedCell();
    const recorded = recordedN(row);
    const label = spec.short || spec.label;
    return `<span class="cell-score ${spec.tone || "cell-measured"}">${escapeHtml(label)} ${
      row.solved || 0
    }/${recorded}</span>`;
  }

  function categoryLine(task) {
    const bits = [categoryLabel(task.category)];
    const subs = subcategories(task).map(subcategoryLabel).filter(Boolean);
    if (subs.length) bits.push(subs.join(" · "));
    return bits.join(" / ");
  }

  function trackPills(task) {
    const bn = batchNum(task);
    const batch = bn
      ? `<span class="pill-track batch">B${batchLabel(bn)}</span>`
      : "";
    return `<span class="pill-track">TB 2.1</span>${batch}`;
  }

  function frozenCounts() {
    const counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    tasks.forEach((task) => {
      const n = batchNum(task);
      if (n) counts[n] += 1;
    });
    return counts;
  }

  function languageCounts() {
    const counts = new Map();
    tasks.forEach((task) => {
      const seen = new Set();
      languageSet(task).forEach((lang) => {
        if (seen.has(lang)) return;
        seen.add(lang);
        counts.set(lang, (counts.get(lang) || 0) + 1);
      });
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }

  function makeChip(key, label, pressed, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
    button.addEventListener("click", onClick);
    return button;
  }

  function renderChips() {
    const counts = corpus.lab.category_mix || {};
    const frozen = frozenCounts();
    const scopeEl = document.getElementById("chips-scope");
    const catEl = document.getElementById("chips-category");
    const langEl = document.getElementById("chips-lang");
    if (!scopeEl || !catEl || !langEl) return;

    const apply = () => {
      setUrl({ surface: "tasks", filter: category, lang: langFilter, push: true });
      renderChips();
      renderCatalog();
      const slug = currentSlug();
      if (slug) renderPanel(bySlug.get(slug) || null);
    };

    scopeEl.innerHTML = "";
    const scopeKeys = [
      ["all", `All ${tasks.length}`],
      ["frozen", `Frozen ${Object.values(frozen).reduce((a, n) => a + n, 0)}`],
      ["b01", `B01 ${frozen[1] || 0}`],
      ["b02", `B02 ${frozen[2] || 0}`],
      ["b03", `B03 ${frozen[3] || 0}`],
      ["b04", `B04 ${frozen[4] || 0}`],
      ["b05", `B05 ${frozen[5] || 0}`],
      ["measured", `Jobs ${corpus.lab.measured_size || 0}`],
      ["agents", `Agent trials ${tasks.filter(hasAgentJobs).length}`],
    ];
    scopeKeys.forEach(([key, label]) => {
      const pressed =
        key === category || (key === "b01" && (category === "batch" || category === "b01"));
      scopeEl.appendChild(
        makeChip(key, label, pressed, () => {
          category = key === "b01" && category === "batch" ? "b01" : key;
          apply();
        })
      );
    });

    catEl.innerHTML = "";
    catEl.appendChild(
      makeChip("cat-all", "All categories", !CATEGORY_LABELS[category], () => {
        if (CATEGORY_LABELS[category]) category = "all";
        apply();
      })
    );
    Object.keys(CATEGORY_LABELS).forEach((key) => {
      catEl.appendChild(
        makeChip(key, `${categoryLabel(key)} ${counts[key] || 0}`, category === key, () => {
          category = key;
          apply();
        })
      );
    });

    langEl.innerHTML = "";
    langEl.appendChild(
      makeChip("lang-all", "All languages", langFilter === "all", () => {
        langFilter = "all";
        apply();
      })
    );
    languageCounts().forEach(([lang, n]) => {
      langEl.appendChild(
        makeChip(lang, `${lang} ${n}`, normalizeLang(langFilter) === lang, () => {
          langFilter = lang;
          apply();
        })
      );
    });
  }

  function renderTable() {
    const selected = currentSlug();
    const visible = tasks.filter(matches);
    rowsEl.innerHTML = "";
    visible.forEach((task) => {
      const tr = document.createElement("tr");
      tr.dataset.slug = task.slug;
      tr.setAttribute("aria-selected", task.slug === selected ? "true" : "false");
      tr.tabIndex = 0;
      const hard =
        String(task.difficulty || "").toLowerCase() === "hard"
          ? ""
          : `<span class="chip chip-warn">difficulty: ${escapeHtml(task.difficulty || "unknown")}</span>`;
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}
          <span class="cat-line">${escapeHtml(categoryLine(task))}${hard}</span>
        </td>
        <td><div class="track-cell">${trackPills(task)}</div></td>
        ${FEATURED_MODELS.map((spec) => `<td class="measured">${modelCell(task, spec)}</td>`).join("")}
      `;
      tr.addEventListener("click", () => selectTask(task.slug, true));
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectTask(task.slug, true);
        }
      });
      rowsEl.appendChild(tr);
    });
  }

  function renderCards() {
    if (!cardsEl) return;
    const selected = currentSlug();
    const visible = tasks.filter(matches);
    cardsEl.innerHTML = "";
    visible.forEach((task) => {
      const article = document.createElement("article");
      article.className = "world-card";
      article.dataset.slug = task.slug;
      article.setAttribute("aria-selected", task.slug === selected ? "true" : "false");
      article.tabIndex = 0;
      const langs = languageSet(task)
        .map((lang) => `<span class="chip chip-lang">${escapeHtml(lang)}</span>`)
        .join("");
      const hard =
        String(task.difficulty || "").toLowerCase() === "hard"
          ? `<span class="pill-hard">Hard</span>`
          : `<span class="chip chip-warn">${escapeHtml(task.difficulty || "unknown")}</span>`;
      article.innerHTML = `
        <p class="world-card-meta">${trackPills(task)}${hard}</p>
        <h3>${escapeHtml(task.name)}</h3>
        <p class="cat-line">${escapeHtml(categoryLine(task))}</p>
        <p class="world-card-langs">${langs || "—"}</p>
        <div class="world-card-models">${FEATURED_MODELS.map((spec) => modelCell(task, spec)).join("")}</div>
      `;
      article.addEventListener("click", () => selectTask(task.slug, true));
      article.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectTask(task.slug, true);
        }
      });
      cardsEl.appendChild(article);
    });
  }

  function renderCatalog() {
    const tableWrap = document.getElementById("catalog-table-wrap");
    const selected = currentSlug();
    const visible = tasks.filter(matches);
    const selectedTask = selected ? bySlug.get(selected) : null;
    const outside = Boolean(selectedTask && !matches(selectedTask));
    if (shownEl) {
      shownEl.textContent = outside
        ? `${visible.length} of ${tasks.length} · selected pack is outside this filter`
        : `${visible.length} of ${tasks.length}`;
    }
    const tableBtn = document.getElementById("view-table");
    const cardsBtn = document.getElementById("view-cards");
    if (tableBtn) tableBtn.setAttribute("aria-pressed", catalogView === "table" ? "true" : "false");
    if (cardsBtn) cardsBtn.setAttribute("aria-pressed", catalogView === "cards" ? "true" : "false");
    if (catalogView === "cards") {
      if (tableWrap) tableWrap.hidden = true;
      if (cardsEl) cardsEl.hidden = false;
      renderCards();
    } else {
      if (tableWrap) tableWrap.hidden = false;
      if (cardsEl) cardsEl.hidden = true;
      renderTable();
    }
  }

  function fileList(task) {
    return (task.files || [])
      .map((file) => {
        const ok = file.exists ? "present" : "missing";
        return `<li><a href="${escapeHtml(file.href)}">${escapeHtml(file.label)}</a> · ${ok}</li>`;
      })
      .join("");
  }

  function harborLine(task) {
    const agents = agentModels(task).filter((row) => recordedN(row) > 0);
    if (!agents.length) return QUEUED_LABEL;
    return agents
      .map((row) => `${shortModel(row.model)} ${row.solved || 0}/${recordedN(row)} recorded`)
      .join(" · ");
  }

  function renderPanel(task) {
    const kicker = document.querySelector("#panel .panel-kicker");
    if (!task) {
      if (kicker) kicker.textContent = "Selected pack";
      panelTitle.textContent = "Choose a row";
      panelEmpty.hidden = false;
      panelEmpty.innerHTML = `
        <p>Select a pack to open its summary, Harbor files, and honest measurement status.</p>
        <p class="hint">Deep links use <code>lab/index.html?surface=tasks&amp;task=&lt;slug&gt;</code>. Default filter is all 100.</p>
      `;
      panelBody.hidden = true;
      panelBody.innerHTML = "";
      return;
    }
    panelEmpty.hidden = true;
    panelBody.hidden = false;
    panelTitle.textContent = task.name;
    if (kicker) {
      kicker.textContent = matches(task)
        ? "Selected pack"
        : "Selected pack (outside current filter)";
    }
    const agents = agentModels(task).filter((row) => recordedN(row) > 0);
    const completed = agents.reduce((sum, row) => sum + (row.solved || 0) + (row.valid_fail || 0), 0);
    const solved = agents.reduce((sum, row) => sum + (row.solved || 0), 0);
    const fails = agents.reduce((sum, row) => sum + (row.valid_fail || 0), 0);
    const bn = batchNum(task);
    const hard =
      String(task.difficulty || "").toLowerCase() === "hard"
        ? `<span class="pill-hard">Hard</span>`
        : `<span class="chip chip-warn">${escapeHtml(task.difficulty || "unknown")}</span>`;
    const langs = languageSet(task)
      .map((lang) => `<span class="chip chip-lang">${escapeHtml(lang)}</span>`)
      .join(" ");
    const featuredHtml = FEATURED_MODELS.map((spec) => {
      if (spec.placeholder) {
        return `<div>${escapeHtml(spec.label)}: <span class="muted">${QUEUED_LABEL}</span></div>`;
      }
      const row = featuredRow(task, spec);
      if (!row) return `<div>${escapeHtml(spec.label)}: <span class="muted">${QUEUED_LABEL}</span></div>`;
      return `<div>${escapeHtml(spec.label)}: ${row.solved || 0}/${recordedN(row)} recorded</div>`;
    }).join("");
    const otherAgents = agents.filter(
      (row) => !/opus-5|gpt-5\.6-sol/i.test(row.model || "")
    );
    const otherHtml = otherAgents.length
      ? otherAgents
          .map((row) => `<div>${escapeHtml(shortModel(row.model))}: ${row.solved || 0}/${recordedN(row)} recorded</div>`)
          .join("")
      : "";
    const measured = hasAgentJobs(task);
    const statusHead = measured ? "Measured" : "Eval queued — no credits";
    const statusBody = measured
      ? `${solved} solved · ${fails} valid fail · ${completed} completed Harbor trials. ${harborLine(task)}.`
      : "No terminus-2 trials ingested for this pack. Grok 4.6, GLM, and Kimi were not run.";
    const themes = ((task.analysis && task.analysis.themes) || []).slice(0, 6);
    panelBody.innerHTML = `
      <dl class="meta">
        <dt>Category</dt>
        <dd>${escapeHtml(categoryLine(task))}</dd>
        <dt>Difficulty / horizon</dt>
        <dd>${hard} <span class="muted">TB 2.1-style · author-labeled ${escapeHtml(
          task.difficulty || "unknown"
        )} · Harbor 0.22</span></dd>
        <dt>Languages</dt>
        <dd>${langs || "—"}</dd>
        <dt>UUID</dt>
        <dd class="mono">${escapeHtml(task.uuid)}</dd>
        <dt>Slug</dt>
        <dd class="mono">${escapeHtml(task.slug)}</dd>
        <dt>Oracle / tests</dt>
        <dd>
          <span class="chip ${task.has_oracle ? "chip-ok" : "chip-muted"}">${
            task.has_oracle ? "oracle" : "no oracle"
          }</span>
          <span class="chip ${task.has_tests ? "chip-ok" : "chip-muted"}">${
            task.has_tests ? "tests" : "no tests"
          }</span>
        </dd>
        <dt>Track</dt>
        <dd><div class="track-cell">${trackPills(task)}</div> ${bn ? `<span class="muted">frozen batch ${batchLabel(bn)}</span>` : `<span class="muted">gallery</span>`}</dd>
        <dt>Featured models</dt>
        <dd>${featuredHtml}${otherHtml}</dd>
        <dt>Status</dt>
        <dd>
          <div class="status-block">
            <p class="status-head">${statusHead}</p>
            <p>${escapeHtml(statusBody)}</p>
          </div>
        </dd>
      </dl>
      ${
        themes.length
          ? `<h3>Analysis</h3><ul class="plain-list">${themes
              .map((theme) => `<li>${escapeHtml(theme)}</li>`)
              .join("")}</ul>`
          : ""
      }
      <p class="panel-summary">${escapeHtml(task.summary || "")}</p>
      <h3>Harbor files</h3>
      <ul class="files">${fileList(task)}</ul>
    `;
  }

  function selectTask(slug, push) {
    const task = bySlug.get(slug);
    setUrl({ slug, surface: "tasks", push });
    showSurface("tasks");
    renderNav();
    renderChips();
    renderCatalog();
    if (!task) {
      renderPanel(null);
      panelTitle.textContent = "Unknown pack";
      panelEmpty.hidden = false;
      panelEmpty.textContent = `No lab row for ?task=${slug}`;
      return;
    }
    renderPanel(task);
    const row =
      rowsEl.querySelector(`[data-slug="${CSS.escape(slug)}"]`) ||
      (cardsEl && cardsEl.querySelector(`[data-slug="${CSS.escape(slug)}"]`));
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  function formatIngestDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  }

  function harborStats() {
    let recorded = 0;
    let solved = 0;
    let validFail = 0;
    let infra = 0;
    let timeout = 0;
    let opusTasks = 0;
    let gptTasks = 0;
    tasks.forEach((task) => {
      agentModels(task).forEach((row) => {
        const n = recordedN(row);
        if (!n) return;
        recorded += n;
        solved += row.solved || 0;
        validFail += row.valid_fail || 0;
        infra += row.infra_error || 0;
        timeout += row.timeout || 0;
        if (/opus-5/i.test(row.model || "")) opusTasks += 1;
        if (/gpt-5\.6-sol/i.test(row.model || "")) gptTasks += 1;
      });
    });
    return {
      recorded,
      solved,
      validFail,
      completed: solved + validFail,
      infra,
      timeout,
      opusTasks,
      gptTasks,
      jobs: tasks.filter(hasJobs).length,
      agents: tasks.filter(hasAgentJobs).length,
    };
  }

  function renderBanners(stats) {
    stats = stats || harborStats();
    const peach = document.getElementById("banner-scores");
    if (peach) {
      peach.textContent = `Recorded Harbor scores only. ${
        corpus.lab.inventory_size || 448
      } authored inventory · ${corpus.lab.mvp_size || 100} public TB 2.1-style packages. Last ingest ${formatIngestDate(
        corpus.lab.generated_utc
      )}. ${stats.jobs} of ${tasks.length} gallery rows have jobs. Remaining eval queued — no credits.`;
    }
  }

  function renderOverview() {
    const stats = harborStats();
    const packs = document.getElementById("stat-packs");
    const packsNote = document.getElementById("stat-packs-note");
    const last = document.getElementById("stat-last");
    const lastNote = document.getElementById("stat-last-note");
    const valid = document.getElementById("stat-valid");
    const validNote = document.getElementById("stat-valid-note");
    if (packs) packs.textContent = String(corpus.lab.mvp_size || tasks.length);
    if (packsNote) {
      packsNote.textContent = `${corpus.lab.mvp_size || tasks.length} public · ${
        corpus.lab.inventory_size || 448
      } inventory`;
    }
    if (last) last.textContent = formatIngestDate(corpus.lab.generated_utc);
    if (lastNote) {
      lastNote.textContent =
        stats.opusTasks || stats.gptTasks
          ? `Opus 5 · gpt-5.6-sol · ${stats.jobs} packs with jobs`
          : "No featured-model ingest yet";
    }
    if (valid) valid.textContent = String(stats.completed);
    if (validNote) {
      validNote.textContent = `${stats.recorded} recorded · infra ${stats.infra} · timeout ${stats.timeout} excluded`;
    }
    renderBanners(stats);
    const grid = document.getElementById("pack-grid");
    if (!grid) return;
    const ordered = [...tasks].sort((a, b) => Number(hasJobs(b)) - Number(hasJobs(a)) || a.name.localeCompare(b.name));
    grid.innerHTML = "";
    ordered.forEach((task) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pack-card";
      btn.dataset.slug = task.slug;
      const hard =
        String(task.difficulty || "").toLowerCase() === "hard"
          ? `<span class="pill-hard">Hard</span>`
          : `<span class="chip chip-warn">${escapeHtml(task.difficulty || "unknown")}</span>`;
      btn.innerHTML = `
        <p class="pack-card-meta">${trackPills(task)}${hard}</p>
        <h3>${escapeHtml(task.name)}</h3>
        <p class="cat-line">${escapeHtml(categoryLine(task))}</p>
        <div class="pack-card-models">${FEATURED_MODELS.map((spec) => modelCell(task, spec)).join("")}</div>
      `;
      btn.addEventListener("click", () => selectTask(task.slug, true));
      grid.appendChild(btn);
    });
  }

  function renderChallengeSlices() {
    const el = document.getElementById("challenge-slices");
    if (!el) return;
    const mix = corpus.lab.category_mix || {};
    const frozen = frozenCounts();
    const stops = corpus.lab.stops || {};
    const domainCards = Object.keys(CATEGORY_LABELS).map((key) => {
      const n = mix[key] || 0;
      const jobs = tasks.filter((task) => task.category === key && hasJobs(task)).length;
      return `<button type="button" class="slice-card" data-filter="${escapeHtml(key)}">
        <p class="pack-card-meta"><span class="pill-track">TB 2.1</span><span class="pill-hard">Hard</span></p>
        <h3>${escapeHtml(categoryLabel(key))}</h3>
        <p class="cat-line">${n} of 100 public packs · ${jobs} with Harbor jobs</p>
        <p class="muted">${jobs ? `${jobs} measured from ingest` : QUEUED_LABEL}</p>
      </button>`;
    });
    const batchCards = [1, 2, 3, 4, 5].map((n) => {
      const size = frozen[n] || 0;
      const slugs = ((corpus.lab.batches || {})[String(n)] || {}).slugs || [];
      const jobs = slugs.filter((slug) => {
        const task = bySlug.get(slug);
        return task && hasJobs(task);
      }).length;
      const stop = stops[String(n)];
      const note = stop
        ? `Stopped: ${stop.reason || "credit/quota"}`
        : jobs
          ? `${jobs} with Harbor jobs`
          : "Frozen · not run";
      return `<button type="button" class="slice-card" data-filter="b${String(n).padStart(2, "0")}">
        <p class="pack-card-meta"><span class="pill-track batch">B${batchLabel(n)}</span><span class="pill-track">TB 2.1</span></p>
        <h3>Frozen ten ${batchLabel(n)}</h3>
        <p class="cat-line">${size}/10 seats from the 100</p>
        <p class="muted">${escapeHtml(note)}</p>
      </button>`;
    });
    el.innerHTML = domainCards.join("") + batchCards.join("");
    el.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        category = btn.getAttribute("data-filter");
        langFilter = "all";
        setUrl({ surface: "tasks", filter: category, slug: "", push: true });
        renderAll();
      });
    });
  }

  function renderCoverage() {
    const table = document.getElementById("coverage-table");
    if (!table) return;
    const cov = (corpus.lab && corpus.lab.coverage) || { domains: [], languages: [], cells: {} };
    const langs = cov.languages || [];
    const domains = cov.domains || Object.keys(CATEGORY_LABELS);
    let html = "<thead><tr><th>Domain</th>";
    langs.forEach((lang) => {
      html += `<th>${escapeHtml(lang)}</th>`;
    });
    html += "</tr></thead><tbody>";
    domains.forEach((domain) => {
      html += `<tr><th scope="row">${escapeHtml(categoryLabel(domain))}</th>`;
      langs.forEach((lang) => {
        const cell = (cov.cells || {})[`${domain}|${lang}`] || { gallery: 0, selected: 0, measured: 0, slugs: [] };
        if (!cell.gallery) {
          html += "<td class='empty-cell'></td>";
          return;
        }
        const marks = (cell.slugs || [])
          .map((slug) => {
            const task = bySlug.get(slug);
            return task && batchNum(task) ? batchLabel(batchNum(task)) : "";
          })
          .filter(Boolean);
        const uniq = [...new Set(marks)];
        const cls = cell.measured ? "cell-measured" : cell.selected ? "cell-selected" : "";
        html += `<td class="${cls}">${cell.gallery}${
          uniq.length ? ` <span class="batch-mark">${uniq.join(",")}</span>` : ""
        }${cell.measured ? ` <span class="chip chip-ok">jobs</span>` : ""}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody>";
    table.innerHTML = html;
  }

  function classDot(cls) {
    if (cls === "solved") return "run-dot solved";
    if (cls === "valid_fail") return "run-dot fail";
    if (cls === "timeout") return "run-dot timeout";
    if (cls === "infra_error") return "run-dot infra";
    return "run-dot unknown";
  }

  function trialsByModel(task) {
    const map = new Map();
    ((task.rollouts && task.rollouts.trials) || []).forEach((trial) => {
      if (isOracleModel(trial.model)) return;
      const key = trial.model || "unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(trial);
    });
    return map;
  }

  function withFocusedTask(rows) {
    const slug = currentSlug();
    if (!slug) return rows;
    const focus = rows.filter((task) => task.slug === slug);
    const rest = rows.filter((task) => task.slug !== slug);
    return focus.concat(rest);
  }

  function renderRuns() {
    const el = document.getElementById("runs-body");
    if (!el) return;
    const rows = withFocusedTask(tasks.filter((task) => batchNum(task) || hasAgentJobs(task)));
    if (!rows.length) {
      el.innerHTML = `<article class="empty-card"><h2>No frozen packages yet</h2><p>Freeze a batch, then ingest Harbor jobs. Dots appear only for recorded trials.</p></article>`;
      return;
    }
    el.innerHTML = rows
      .map((task) => {
        const groups = trialsByModel(task);
        const body = [...groups.entries()]
          .map(([model, trials]) => {
            const dots = trials
              .map(
                (trial) =>
                  `<span class="${classDot(trial.classification)}" title="${escapeHtml(
                    trial.classification
                  )}"></span>`
              )
              .join("");
            return `<div class="run-row"><span class="run-model">${escapeHtml(
              shortModel(model)
            )}</span><span class="run-dots">${dots || '<span class="muted">none</span>'}</span><span class="muted">${
              trials.length
            } recorded</span></div>`;
          })
          .join("");
        return `<article class="chart-card"><h2>${escapeHtml(task.name)}</h2>
          <p class="slug">${escapeHtml(task.slug)}${
            batchNum(task) ? " · batch " + batchLabel(batchNum(task)) : ""
          }</p>
          ${body || `<p class="muted">${QUEUED_LABEL}</p>`}
        </article>`;
      })
      .join("");
  }

  function renderTraces() {
    const el = document.getElementById("traces-body");
    if (!el) return;
    const focus = currentSlug() ? bySlug.get(currentSlug()) : null;
    const rows = (focus ? [focus] : tasks.filter(hasAgentJobs)).slice(0, 12);
    if (!rows.length) {
      el.innerHTML = `<article class="empty-card"><h2>No private Harbor trials are recorded</h2><p>Traces stay empty until terminus-2 writes trajectory.json under jobs/.</p></article>`;
      return;
    }
    el.innerHTML = rows
      .map((task) => {
        const trials = ((task.rollouts && task.rollouts.trials) || []).filter((row) => !isOracleModel(row.model));
        const cards = trials
          .slice(0, 8)
          .map(
            (trial) => `<article class="trace-card">
              <p><strong>${escapeHtml(shortModel(trial.model))}</strong> · ${escapeHtml(
                trial.classification
              )}</p>
              <p class="muted">${escapeHtml((trial.summary || "No readable steps.").slice(0, 700))}</p>
            </article>`
          )
          .join("");
        return `<h2>${escapeHtml(task.name)}</h2>${cards || `<p class="muted">${QUEUED_LABEL}</p>`}`;
      })
      .join("");
  }

  function renderFailures() {
    const el = document.getElementById("failures-body");
    if (!el) return;
    const rows = withFocusedTask(
      tasks.filter((task) => task.analysis && (task.analysis.themes || []).length)
    );
    if (!rows.length) {
      el.innerHTML = `<article class="empty-card"><h2>No failure map yet</h2><p>Ingest valid-fail traces to list named verifier holes. We do not copy another lab’s rubric.</p></article>`;
      return;
    }
    el.innerHTML = rows
      .map((task) => {
        const tests = (task.analysis.failing_tests || [])
          .slice(0, 8)
          .map((name) => `<li><code>${escapeHtml(name)}</code></li>`)
          .join("");
        const themes = (task.analysis.themes || [])
          .slice(0, 8)
          .map((theme) => `<li>${escapeHtml(theme)}</li>`)
          .join("");
        return `<article class="chart-card"><h2>${escapeHtml(task.name)}</h2>
          <p class="slug">${escapeHtml(task.slug)}</p>
          ${tests ? `<h3>Failing tests</h3><ul class="plain-list">${tests}</ul>` : ""}
          <h3>Themes</h3><ul class="plain-list">${themes}</ul>
        </article>`;
      })
      .join("");
  }

  function renderVerifier() {
    const el = document.getElementById("verifier-kpis");
    if (!el) return;
    const frozen = tasks.filter((task) => batchNum(task));
    const oracleOk = frozen.filter((task) => (oracleModels(task)[0] || {}).solved).length;
    const measured = frozen.filter(hasJobs).length;
    const infra = frozen.reduce(
      (s, task) => s + agentModels(task).reduce((n, row) => n + (row.infra_error || 0), 0),
      0
    );
    el.innerHTML = `
      <article class="chart-card"><p class="stat-label">Frozen packages</p><p class="stat-value">${frozen.length}</p></article>
      <article class="chart-card"><p class="stat-label">Oracle ingested pass</p><p class="stat-value">${oracleOk}</p></article>
      <article class="chart-card"><p class="stat-label">With Harbor jobs</p><p class="stat-value">${measured}</p></article>
      <article class="chart-card"><p class="stat-label">Infra trials</p><p class="stat-value">${infra}</p><p class="stat-note">Excluded from completed counts</p></article>
    `;
  }

  function renderHarness() {
    const el = document.getElementById("harness-measured");
    if (!el) return;
    const h = corpus.lab.harness || {};
    el.innerHTML = `
      <dt>Agent</dt><dd>${escapeHtml(h.agent || "terminus-2")}</dd>
      <dt>Oracle</dt><dd>${escapeHtml(h.oracle || "oracle")}</dd>
      <dt>Empty</dt><dd>${escapeHtml(h.empty || "nop")} (optional)</dd>
      <dt>Harbor</dt><dd>${escapeHtml(h.harbor || "0.22")}</dd>
      <dt>Planned attempts</dt><dd>${escapeHtml(String(h.planned_attempts || PLANNED))} independent trials (-k)</dd>
      <dt>n_trials</dt><dd>${escapeHtml(h.n_trials || "n_attempts × tasks × agents")}</dd>
    `;
  }

  function renderBatches() {
    const el = document.getElementById("batches-body");
    if (!el) return;
    const meta = corpus.lab.batches || {};
    const stops = corpus.lab.stops || {};
    const stoppedBatch = Object.keys(stops).map(Number).filter((n) => n > 0);
    const earliestStop = stoppedBatch.length ? Math.min(...stoppedBatch) : 0;
    const stopBanner = document.getElementById("batches-stop");
    if (stopBanner) {
      const bits = Object.keys(stops)
        .sort()
        .map((key) => {
          const stop = stops[key] || {};
          return `Batch ${String(key).padStart(2, "0")} stopped (${stop.reason || "credit/quota"}). Later frozen tens were not run.`;
        });
      stopBanner.hidden = bits.length === 0;
      stopBanner.textContent = bits.join(" ");
    }
    el.innerHTML = [1, 2, 3, 4, 5]
      .map((n) => {
        const info = meta[String(n)] || { size: 0, slugs: [] };
        const slugs = info.slugs || [];
        const frozen = slugs.length;
        const withJobs = slugs.filter((slug) => {
          const task = bySlug.get(slug);
          return task && hasJobs(task);
        }).length;
        const withAgents = slugs.filter((slug) => {
          const task = bySlug.get(slug);
          return task && hasAgentJobs(task);
        }).length;
        const stop = stops[String(n)];
        let status = !frozen
          ? "not frozen"
          : withAgents === 10
            ? "measured"
            : withJobs
              ? "partial"
              : "not run";
        if (stop) {
          status = `STOPPED: ${stop.reason || "credit/quota"}`;
        } else if (earliestStop && n > earliestStop) {
          status = `frozen · not run (stopped at batch ${String(earliestStop).padStart(2, "0")})`;
        } else if (!withJobs) {
          status = "frozen · not run";
        }
        return `<article class="chart-card">
          <p class="stat-label">Batch ${batchLabel(n)}</p>
          <p class="stat-value">${frozen}/10</p>
          <p class="stat-note">${withJobs} with jobs · ${withAgents} with agents · ${escapeHtml(status)}</p>
        </article>`;
      })
      .join("");
  }

  function aggregateAgents() {
    const map = new Map();
    tasks.forEach((task) => {
      agentModels(task).forEach((row) => {
        const key = row.model || "unknown";
        const cur = map.get(key) || {
          model: key,
          tasks: 0,
          n: 0,
          solved: 0,
          valid_fail: 0,
          infra_error: 0,
          timeout: 0,
          unknown: 0,
        };
        cur.tasks += 1;
        cur.n += row.n || 0;
        cur.solved += row.solved || 0;
        cur.valid_fail += row.valid_fail || 0;
        cur.infra_error += row.infra_error || 0;
        cur.timeout += row.timeout || 0;
        cur.unknown += row.unknown || 0;
        map.set(key, cur);
      });
    });
    return [...map.values()];
  }

  function aggregateFeatured(spec) {
    if (spec.placeholder) {
      return {
        status: "queued",
        tasks: 0,
        n: 0,
        solved: 0,
        note: QUEUED_LABEL,
      };
    }
    let tasksN = 0;
    let n = 0;
    let solved = 0;
    tasks.forEach((task) => {
      const row = featuredRow(task, spec);
      if (!row) return;
      tasksN += 1;
      n += recordedN(row);
      solved += row.solved || 0;
    });
    if (!n) {
      return { status: "queued", tasks: 0, n: 0, solved: 0, note: "No Harbor ingest for this slug on the 100." };
    }
    return {
      status: "recorded",
      tasks: tasksN,
      n,
      solved,
      note: "Harbor ingest only. Denominator is recorded trials, never padded.",
    };
  }

  function renderModels() {
    const banner = document.getElementById("models-banner");
    if (banner) {
      banner.textContent =
        "448 authored packages. 100 public. Private Harbor trials where recorded (Batch 01, partial). Grok 4.6, GLM, and Kimi are eval queued — no credits, not estimates.";
    }
    const summary = document.getElementById("models-summary-rows");
    if (summary) {
      summary.innerHTML = FEATURED_MODELS.map((spec) => {
        const agg = aggregateFeatured(spec);
        const cell =
          agg.status === "queued"
            ? `<span class="cell-queued">${QUEUED_LABEL}</span>`
            : `<span class="cell-score cell-measured">${agg.solved}/${agg.n}</span>`;
        const tasksCell = agg.status === "queued" ? "—" : String(agg.tasks);
        return `<tr>
          <td class="name">${escapeHtml(spec.label)}<span class="slug">${escapeHtml(spec.slug)}</span></td>
          <td>${agg.status === "queued" ? `<span class="chip chip-muted">queued</span>` : `<span class="chip chip-ok">recorded</span>`}</td>
          <td>${tasksCell}</td>
          <td>${cell}</td>
          <td class="muted">${escapeHtml(agg.note)}</td>
        </tr>`;
      }).join("");
    }
    const matrix = document.getElementById("models-matrix-rows");
    if (!matrix) return;
    matrix.innerHTML = "";
    tasks.forEach((task) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}<span class="cat-line">${escapeHtml(categoryLine(task))}</span></td>
        <td><div class="track-cell">${trackPills(task)}</div></td>
        ${FEATURED_MODELS.map((spec) => `<td class="measured">${modelCell(task, spec)}</td>`).join("")}
      `;
      tr.addEventListener("click", () => selectTask(task.slug, true));
      matrix.appendChild(tr);
    });
  }

  function renderAgents() {
    const empty = document.getElementById("agents-empty");
    const body = document.getElementById("agents-body");
    if (!empty || !body) return;
    const rows = aggregateAgents();
    if (!rows.length) {
      empty.hidden = false;
      body.hidden = true;
      return;
    }
    empty.hidden = true;
    body.hidden = false;
    const summary = document.getElementById("agents-summary");
    const frozenN = tasks.filter((task) => batchNum(task)).length || 10;
    summary.innerHTML = rows
      .map((row, i) => {
        const planned = frozenN * PLANNED;
        const pct = Math.min(100, Math.round((row.n / Math.max(planned, 1)) * 100));
        return `<div class="model-line"><span class="dot${
          i ? " dot-alt" : ""
        }"></span><strong>${escapeHtml(shortModel(row.model))}</strong>
          <span>${row.solved} solved / ${row.n} recorded on ${row.tasks} task${row.tasks === 1 ? "" : "s"}
          (cheap plan ${planned} = ${frozenN}×${PLANNED})
          <span class="bar-track ${pct >= 100 ? "" : "partial"}"><b style="width:${pct}%"></b></span></span></div>`;
      })
      .join("");

    const tbody = document.getElementById("agent-rows");
    tbody.innerHTML = rows
      .map((row, i) => {
        return `<tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(shortModel(row.model))}<span class="slug">${escapeHtml(row.model)}</span></td>
          <td>terminus-2</td>
          <td>${row.tasks}</td>
          <td>${row.n} <span class="muted">recorded trials</span></td>
          <td>${row.solved}</td>
          <td>${row.valid_fail}</td>
          <td>${row.infra_error}</td>
          <td>${row.timeout}</td>
        </tr>`;
      })
      .join("");

    const breakdown = document.getElementById("agent-task-breakdown");
    const agentTasks = tasks.filter(hasAgentJobs);
    breakdown.innerHTML = `<h2>By task</h2><p class="muted">Denominator is recorded Harbor trials for that model, not a padded ${PLANNED}. A 1-trial cheap probe shows 0/1, not 0/${PLANNED}. Infra and timeout are listed and excluded from completed counts.</p>
      <div class="table-card"><div class="table-scroll"><table>
        <thead><tr><th>Task</th><th>Model</th><th>Recorded</th><th>Solved</th><th>Valid fail</th><th>Infra</th><th>Timeout</th></tr></thead>
        <tbody>${agentTasks
          .flatMap((task) =>
            agentModels(task).map(
              (row) => `<tr>
                <td class="name">${escapeHtml(task.name)}<span class="slug">${escapeHtml(task.slug)}</span></td>
                <td>${escapeHtml(shortModel(row.model))}</td>
                <td>${recordedN(row)}</td>
                <td>${row.solved || 0}</td>
                <td>${row.valid_fail || 0}</td>
                <td>${row.infra_error || 0}</td>
                <td>${row.timeout || 0}</td>
              </tr>`
            )
          )
          .join("")}</tbody></table></div></div>`;
  }

  function renderTasksSub() {
    const el = document.getElementById("tasks-sub");
    if (!el) return;
    const jobs = tasks.filter(hasJobs).length;
    const frozen = tasks.filter((task) => batchNum(task)).length;
    const hard = tasks.filter((t) => String(t.difficulty || "").toLowerCase() === "hard").length;
    el.textContent = `${tasks.length} gallery packages · ${
      corpus.lab.inventory_size
    } inventory · ${hard} hard · ${frozen} frozen · ${jobs} with Harbor jobs · featured model cells are ingest-only`;
  }

  function renderAll() {
    const surface = currentSurface();
    category = params().get("filter") || "all";
    langFilter = params().get("lang") || "all";
    catalogView = params().get("view") === "cards" ? "cards" : "table";
    renderNav();
    showSurface(surface);
    renderBanners();
    if (surface === "overview") renderOverview();
    if (surface === "challenges") {
      renderChallengeSlices();
      renderCoverage();
    }
    if (surface === "tasks") {
      renderTasksSub();
      renderChips();
      renderCatalog();
      const slug = currentSlug();
      renderPanel(slug ? bySlug.get(slug) : null);
    }
    if (surface === "models") renderModels();
    if (surface === "runs") renderRuns();
    if (surface === "traces") renderTraces();
    if (surface === "failures") renderFailures();
    if (surface === "verifier") renderVerifier();
    if (surface === "harness") renderHarness();
    if (surface === "batches") renderBatches();
    if (surface === "agents") renderAgents();
  }

  function bindNav(root) {
    if (!root) return;
    root.addEventListener("click", (event) => {
      const button = event.target.closest("[data-nav]");
      if (!button) return;
      event.preventDefault();
      const id = SURFACE_ALIASES[button.getAttribute("data-nav")] || button.getAttribute("data-nav");
      if (isBlockedSurface(id) || id === "unavailable") return;
      const keepSlug = id === "tasks" || id === "runs" || id === "traces" || id === "failures";
      setUrl({ surface: id, slug: keepSlug ? currentSlug() : "", push: true });
      renderAll();
    });
  }

  bindNav(document.getElementById("nav-main"));
  bindNav(document.querySelector("#surface-unavailable"));
  bindNav(document.querySelector(".packs-head"));

  const brand = document.querySelector(".brand");
  if (brand) {
    brand.addEventListener("click", (event) => {
      event.preventDefault();
      setUrl({ surface: "overview", slug: "", push: true });
      renderAll();
    });
  }

  if (qEl) {
    qEl.addEventListener("input", () => {
      query = qEl.value.trim().toLowerCase();
      renderCatalog();
      const slug = currentSlug();
      if (slug) renderPanel(bySlug.get(slug) || null);
    });
  }

  const viewTable = document.getElementById("view-table");
  const viewCards = document.getElementById("view-cards");
  if (viewTable) {
    viewTable.addEventListener("click", () => {
      catalogView = "table";
      setUrl({ surface: "tasks", view: "table", push: true });
      renderCatalog();
    });
  }
  if (viewCards) {
    viewCards.addEventListener("click", () => {
      catalogView = "cards";
      setUrl({ surface: "tasks", view: "cards", push: true });
      renderCatalog();
    });
  }

  window.addEventListener("popstate", () => renderAll());

  initTheme();
  renderAll();
  const initial = currentSlug();
  if (initial && currentSurface() === "tasks") selectTask(initial, false);
})();

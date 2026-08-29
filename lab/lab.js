(() => {
  const corpus = window.AW_CORPUS;
  const laterModal = document.getElementById("later-modal");
  const laterBody = document.getElementById("later-body");

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

  const SURFACES = [
    "worlds",
    "coverage",
    "catalog",
    "runs",
    "traces",
    "stump",
    "failures",
    "verifier",
    "harness",
    "spend",
    "batches",
    "agents",
  ];

  const SURFACE_ALIASES = {
    overview: "worlds",
    worlds: "worlds",
    coverage: "coverage",
    tasks: "catalog",
    corpus: "catalog",
    catalog: "catalog",
    runs: "runs",
    traces: "traces",
    stump: "stump",
    failures: "failures",
    verifier: "verifier",
    harness: "harness",
    spend: "spend",
    batches: "batches",
    agents: "agents",
  };

  const PLANNED = Number((corpus.lab.harness || {}).planned_attempts) || 5;
  const tasks = corpus.tasks;
  const bySlug = new Map(tasks.map((task) => [task.slug, task]));

  const rowsEl = document.getElementById("rows");
  const chipsEl = document.getElementById("chips");
  const shownEl = document.getElementById("shown");
  const qEl = document.getElementById("q");
  const panelTitle = document.getElementById("panel-title");
  const panelEmpty = document.getElementById("panel-empty");
  const panelBody = document.getElementById("panel-body");

  let category = params().get("filter") || "all";
  let query = "";
  let previewIndex = 0;

  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value;
  }

  function languages(task) {
    return task.languages || [];
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

  function currentSurface() {
    const raw = (params().get("surface") || "").toLowerCase();
    if (raw && SURFACE_ALIASES[raw]) return SURFACE_ALIASES[raw];
    if (currentSlug()) return "catalog";
    const filter = (params().get("filter") || "").toLowerCase();
    if (filter && filter !== "all") return "catalog";
    return "worlds";
  }

  function setUrl({ slug, surface, filter, push }) {
    const url = new URL(window.location.href);
    const nextSlug = slug === undefined ? currentSlug() : slug;
    const nextSurface = surface === undefined ? currentSurface() : surface;
    const nextFilter = filter === undefined ? category : filter;
    if (nextSlug) url.searchParams.set("task", nextSlug);
    else url.searchParams.delete("task");
    if (nextSurface && nextSurface !== "worlds") url.searchParams.set("surface", nextSurface);
    else url.searchParams.delete("surface");
    if (nextFilter && nextFilter !== "all") url.searchParams.set("filter", nextFilter);
    else url.searchParams.delete("filter");
    history[push ? "pushState" : "replaceState"]({ task: nextSlug, surface: nextSurface, filter: nextFilter }, "", url);
  }

  function isOracleModel(name) {
    const value = String(name || "").toLowerCase();
    return !value || value === "oracle" || orIncludesOracle(value);
  }

  function orIncludesOracle(value) {
    return value.includes("oracle");
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

  function matchesFilter(task) {
    if (!task) return false;
    const batchKey = parseBatchFilter(category);
    // filter=batch is Batch 01 (10 of 100), matching ?surface=tasks&filter=batch.
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
    return true;
  }

  function matches(task) {
    if (!matchesFilter(task)) return false;
    if (!query) return true;
    const hay = [task.name, task.slug, task.category, categoryLabel(task.category), languages(task).join(" ")]
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function applyTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute("content", next === "dark" ? "#0C1412" : "#F7F4EE");
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
        if (currentSurface() === "worlds") renderLengthChart();
      });
    }
  }

  function renderNav() {
    const active = currentSurface();
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

  function measuredCell(task) {
    if (!hasJobs(task)) return `<span class="chip chip-muted">—</span>`;
    const agents = agentModels(task);
    if (!agents.length) {
      const oracle = oracleModels(task)[0];
      const ok = oracle && oracle.solved;
      return `<span class="chip chip-oracle">${ok ? "oracle" : "jobs"}</span>`;
    }
    return agents
      .map((row) => {
        const recorded = recordedN(row);
        const cls = recorded >= PLANNED ? "chip-ok" : "chip-warn";
        return `<span class="chip ${cls}">${escapeHtml(shortModel(row.model))} ${row.solved || 0}/${recorded}</span>`;
      })
      .join(" ");
  }

  function frozenCounts() {
    const counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    tasks.forEach((task) => {
      const n = batchNum(task);
      if (n) counts[n] += 1;
    });
    return counts;
  }

  function renderChips() {
    const counts = corpus.lab.category_mix || {};
    const frozen = frozenCounts();
    const keys = [
      "all",
      "batch",
      "frozen",
      "b01",
      "b02",
      "b03",
      "b04",
      "b05",
      "measured",
      "agents",
      ...Object.keys(CATEGORY_LABELS),
    ];
    chipsEl.innerHTML = "";
    keys.forEach((key) => {
      const button = document.createElement("button");
      const b = parseBatchFilter(key);
      let label;
      if (key === "all") label = `All ${tasks.length}`;
      else if (key === "batch") label = `Batch 01 ${frozen[1] || 10}`;
      else if (key === "frozen") label = `Frozen ${Object.values(frozen).reduce((a, n) => a + n, 0)}`;
      else if (b) label = `B${batchLabel(b)} ${frozen[b] || 0}`;
      else if (key === "measured") label = `Jobs ${corpus.lab.measured_size || 0}`;
      else if (key === "agents") label = `Agent trials ${tasks.filter(hasAgentJobs).length}`;
      else label = `${categoryLabel(key)} ${counts[key] || 0}`;
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", key === category ? "true" : "false");
      button.addEventListener("click", () => {
        category = key;
        setUrl({ surface: "catalog", filter: key, push: true });
        renderChips();
        renderTable();
        const slug = currentSlug();
        if (slug) renderPanel(bySlug.get(slug) || null);
      });
      chipsEl.appendChild(button);
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
      const langHtml = languages(task)
        .map((lang) => `<span class="chip chip-lang">${escapeHtml(lang)}</span>`)
        .join(" ");
      const bn = batchNum(task);
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}
          <span class="slug">${escapeHtml(task.slug)}</span>
        </td>
        <td><span class="chip cat-${escapeHtml(task.category)}">${escapeHtml(categoryLabel(task.category))}</span></td>
        <td>${langHtml || "—"}</td>
        <td>${bn ? `<span class="chip chip-batch">${batchLabel(bn)}</span>` : `<span class="muted">—</span>`}</td>
        <td class="measured">${measuredCell(task)}</td>
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
    const selectedTask = selected ? bySlug.get(selected) : null;
    const outside = Boolean(selectedTask && !matches(selectedTask));
    shownEl.textContent = outside
      ? `${visible.length} of ${tasks.length} · selected package is outside this filter`
      : `${visible.length} of ${tasks.length}`;
  }

  function fileList(task) {
    return (task.files || [])
      .map((file) => {
        const ok = file.exists ? "present" : "missing";
        return `<li><a href="${escapeHtml(file.href)}">${escapeHtml(file.label)}</a> · ${ok}</li>`;
      })
      .join("");
  }

  function stumpDisplay(task) {
    if (!hasAgentJobs(task) || task.stump_pct === null || task.stump_pct === undefined) return "—";
    const agents = agentModels(task);
    const completed = agents.reduce((sum, row) => sum + (row.solved || 0) + (row.valid_fail || 0), 0);
    if (!completed) return "—";
    return `${task.stump_pct}%`;
  }

  function renderPanel(task) {
    const kicker = document.querySelector("#panel .panel-kicker");
    if (!task) {
      if (kicker) kicker.textContent = "Selected package";
      panelTitle.textContent = "Choose a row";
      panelEmpty.hidden = false;
      panelEmpty.innerHTML = `
        <p>Select a task to open its summary, Harbor files, and ingest status.</p>
        <p class="hint">Deep links use <code>lab/index.html?surface=catalog&amp;task=&lt;slug&gt;</code>. A <code>filter=</code> chip can stay; <code>task</code> still opens this panel.</p>
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
        ? "Selected package"
        : "Selected package (outside current filter)";
    }
    const agents = agentModels(task);
    const oracle = oracleModels(task)[0];
    const roll = task.rollouts || {};
    const bn = batchNum(task);
    const agentHtml = agents.length
      ? agents
          .map((row) => {
            const recorded = recordedN(row);
            return `<div>${escapeHtml(shortModel(row.model))}: ${row.solved || 0} solved · ${
              row.valid_fail || 0
            } valid fail · ${row.infra_error || 0} infra · ${
              row.timeout || 0
            } timeout · ${recorded} recorded</div>`;
          })
          .join("")
      : `<span class="muted">No terminus-2 trials ingested.</span>`;
    const themes = ((task.analysis && task.analysis.themes) || []).slice(0, 6);
    panelBody.innerHTML = `
      <dl class="meta">
        <dt>Category</dt>
        <dd>${escapeHtml(categoryLabel(task.category))}</dd>
        <dt>Difficulty</dt>
        <dd>${escapeHtml(task.difficulty)} <span class="muted">(author label)</span></dd>
        <dt>Languages</dt>
        <dd>${escapeHtml(languages(task).join(", ") || "—")}</dd>
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
        <dt>Batch</dt>
        <dd>${bn ? batchLabel(bn) + " selected" : "gallery only"}</dd>
        <dt>Harbor jobs</dt>
        <dd>${hasJobs(task) ? escapeHtml(roll.note || "ingested") : "not run"}</dd>
        <dt>Oracle trial</dt>
        <dd>${
          oracle
            ? `${oracle.solved || 0}/${oracle.n || 0} solved`
            : `<span class="muted">not ingested</span>`
        }</dd>
        <dt>Agents</dt>
        <dd>${agentHtml}</dd>
        <dt>Stump %</dt>
        <dd>${escapeHtml(stumpDisplay(task))} <span class="muted">(valid fail / completed; infra excluded)</span></dd>
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
    setUrl({ slug, surface: "catalog", push });
    showSurface("catalog");
    renderNav();
    renderChips();
    renderTable();
    if (!task) {
      renderPanel(null);
      panelTitle.textContent = "Unknown package";
      panelEmpty.hidden = false;
      panelEmpty.textContent = `No lab row for ?task=${slug}`;
      return;
    }
    renderPanel(task);
    const row = rowsEl.querySelector(`[data-slug="${CSS.escape(slug)}"]`);
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  function renderCoverage() {
    const table = document.getElementById("coverage-table");
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

  function renderBars(el, items, max) {
    el.innerHTML = "";
    const peak = max || Math.max(1, ...items.map((item) => item.n));
    items.forEach((item) => {
      const wrap = document.createElement("div");
      wrap.className = "bar";
      const height = Math.max(6, Math.round((item.n / peak) * 110));
      wrap.innerHTML = `<i style="height:${height}px"></i><span>${escapeHtml(item.label)} (${item.n})</span>`;
      el.appendChild(wrap);
    });
  }

  function renderLengthChart() {
    const svg = document.getElementById("chart-length");
    const caption = document.getElementById("chart-length-caption");
    const series = (((corpus.lab.charts || {}).instruction_length || {}).ecdf) || [];
    const stats = (corpus.lab.charts || {}).instruction_length || {};
    if (caption) {
      caption.textContent = stats.n
        ? `n=${stats.n} · median ${stats.median} chars · p25 ${stats.p25} · p75 ${stats.p75} · max ${stats.max}`
        : "No instruction lengths in corpus.";
    }
    if (!svg) return;
    if (series.length < 2) {
      svg.innerHTML = "";
      return;
    }
    const w = 320;
    const h = 140;
    const pad = 18;
    const maxX = series[series.length - 1].chars || 1;
    const pts = series
      .map((point) => {
        const x = pad + (point.chars / maxX) * (w - pad * 2);
        const y = h - pad - point.frac * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    const area = `${pad},${h - pad} ${pts} ${w - pad},${h - pad}`;
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    const stroke = dark ? "#2A9A90" : "#0F766E";
    const fill = dark ? "rgba(42,154,144,0.18)" : "rgba(15,118,110,0.14)";
    svg.innerHTML = `
      <polyline fill="${fill}" stroke="none" points="${area}"></polyline>
      <polyline fill="none" stroke="${stroke}" stroke-width="2" points="${pts}"></polyline>
    `;
  }

  function renderPreview() {
    const previews = corpus.lab.instruction_previews || [];
    const code = document.getElementById("preview-code");
    const meta = document.getElementById("preview-meta");
    const pager = document.getElementById("preview-pager");
    const dots = document.getElementById("preview-dots");
    if (!code) return;
    if (!previews.length) {
      code.textContent = "No instruction previews in corpus.";
      return;
    }
    const item = previews[previewIndex % previews.length];
    if (meta) meta.textContent = `${item.chars} chars · ${item.slug}`;
    code.innerHTML = (item.lines || [])
      .map(
        (line) =>
          `<span class="line"><span class="ln">${line.n}</span><span class="lt">${escapeHtml(line.text || "")}</span></span>`
      )
      .join("");
    if (previews.length > 1 && pager && dots) {
      pager.hidden = false;
      dots.innerHTML = "";
      previews.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        if (i === previewIndex) dot.setAttribute("aria-current", "true");
        dot.addEventListener("click", () => {
          previewIndex = i;
          renderPreview();
        });
        dots.appendChild(dot);
      });
    }
  }

  function renderWorlds() {
    const jobs = tasks.filter(hasJobs).length;
    const agents = tasks.filter(hasAgentJobs).length;
    document.getElementById("stat-packages").textContent = String(corpus.lab.mvp_size || tasks.length);
    document.getElementById("stat-inventory").textContent = String(corpus.lab.inventory_size || 448);
    document.getElementById("stat-batch").textContent = String(corpus.lab.measured_target || 50);
    document.getElementById("stat-measured").textContent = String(jobs);
    document.getElementById("stat-measured-note").textContent =
      `Harbor jobs ingested · ${agents} with agent trials · cheap plan k=${PLANNED}`;

    const domains = Object.keys(CATEGORY_LABELS).map((key) => ({
      label: categoryLabel(key).split(" ")[0],
      n: (corpus.lab.category_mix || {})[key] || 0,
    }));
    renderBars(document.getElementById("chart-domains"), domains);
    const langs = ((corpus.lab.charts || {}).language_mix || []).slice(0, 8).map((row) => ({
      label: row.language,
      n: row.n,
    }));
    renderBars(document.getElementById("chart-langs"), langs);
    renderLengthChart();
    renderPreview();
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

  function renderRuns() {
    const el = document.getElementById("runs-body");
    const rows = tasks.filter((task) => batchNum(task) || hasAgentJobs(task));
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
          ${body || '<p class="muted">Oracle only — no terminus-2 trials.</p>'}
        </article>`;
      })
      .join("");
  }

  function renderTraces() {
    const el = document.getElementById("traces-body");
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
        return `<h2>${escapeHtml(task.name)}</h2>${cards || '<p class="muted">No agent traces.</p>'}`;
      })
      .join("");
  }

  function renderStump() {
    const el = document.getElementById("stump-body");
    const rows = tasks.filter(hasAgentJobs);
    if (!rows.length) {
      el.innerHTML = `<article class="empty-card"><h2>Stump hidden</h2><p>Need at least one completed agent trial (solved or valid fail). Infra and timeout never count.</p></article>`;
      return;
    }
    el.innerHTML = `<div class="table-card"><div class="table-scroll"><table>
      <thead><tr><th>Task</th><th>Batch</th><th>Completed</th><th>Valid fail</th><th>Stump</th><th>Infra</th><th>Timeout</th></tr></thead>
      <tbody>${rows
        .map((task) => {
          const agents = agentModels(task);
          const solved = agents.reduce((s, r) => s + (r.solved || 0), 0);
          const vf = agents.reduce((s, r) => s + (r.valid_fail || 0), 0);
          const infra = agents.reduce((s, r) => s + (r.infra_error || 0), 0);
          const timeout = agents.reduce((s, r) => s + (r.timeout || 0), 0);
          return `<tr>
            <td class="name">${escapeHtml(task.name)}<span class="slug">${escapeHtml(task.slug)}</span></td>
            <td>${batchNum(task) ? batchLabel(batchNum(task)) : "—"}</td>
            <td>${solved + vf}</td>
            <td>${vf}</td>
            <td>${escapeHtml(stumpDisplay(task))}</td>
            <td>${infra}</td>
            <td>${timeout}</td>
          </tr>`;
        })
        .join("")}</tbody></table></div></div>`;
  }

  function renderFailures() {
    const el = document.getElementById("failures-body");
    const rows = tasks.filter((task) => task.analysis && (task.analysis.themes || []).length);
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
    const frozen = tasks.filter((task) => batchNum(task));
    const oracleOk = frozen.filter((task) => (oracleModels(task)[0] || {}).solved).length;
    const measured = frozen.filter(hasJobs).length;
    const infra = frozen.reduce(
      (s, task) => s + agentModels(task).reduce((n, row) => n + (row.infra_error || 0), 0),
      0
    );
    document.getElementById("verifier-kpis").innerHTML = `
      <article class="chart-card"><p class="stat-label">Frozen packages</p><p class="stat-value">${frozen.length}</p></article>
      <article class="chart-card"><p class="stat-label">Oracle ingested pass</p><p class="stat-value">${oracleOk}</p></article>
      <article class="chart-card"><p class="stat-label">With Harbor jobs</p><p class="stat-value">${measured}</p></article>
      <article class="chart-card"><p class="stat-label">Infra trials</p><p class="stat-value">${infra}</p><p class="stat-note">Excluded from stump</p></article>
    `;
  }

  function renderHarness() {
    const h = corpus.lab.harness || {};
    document.getElementById("harness-measured").innerHTML = `
      <dt>Agent</dt><dd>${escapeHtml(h.agent || "terminus-2")}</dd>
      <dt>Oracle</dt><dd>${escapeHtml(h.oracle || "oracle")}</dd>
      <dt>Empty</dt><dd>${escapeHtml(h.empty || "nop")} (optional)</dd>
      <dt>Harbor</dt><dd>${escapeHtml(h.harbor || "0.22")}</dd>
      <dt>Planned attempts</dt><dd>${escapeHtml(String(h.planned_attempts || PLANNED))} independent trials (-k)</dd>
      <dt>n_trials</dt><dd>${escapeHtml(h.n_trials || "n_attempts × tasks × agents")}</dd>
    `;
  }

  function renderSpend() {
    const spend = corpus.lab.spend || {};
    const jobs = spend.jobs || [];
    document.getElementById("spend-total").textContent =
      spend.cost_usd_sum != null ? `$${Number(spend.cost_usd_sum).toFixed(2)}` : "—";
    document.getElementById("spend-note").textContent = spend.note || "";
    const tbody = document.getElementById("spend-rows");
    if (!jobs.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">No Harbor job rollups with cost_usd yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = jobs
      .map(
        (row) => `<tr>
          <td class="mono">${escapeHtml(row.job)}</td>
          <td>${row.n_total_trials ?? "—"}</td>
          <td>${row.n_completed_trials ?? "—"}</td>
          <td>${row.n_errored_trials ?? "—"}</td>
          <td>${row.cost_usd != null ? "$" + Number(row.cost_usd).toFixed(4) : "—"}</td>
        </tr>`
      )
      .join("");
  }

  function renderBatches() {
    const el = document.getElementById("batches-body");
    const meta = corpus.lab.batches || {};
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
        const status = !frozen
          ? "not frozen"
          : withAgents === 10
            ? "measured"
            : withJobs
              ? "partial"
              : "oracle pending / blocked";
        return `<article class="chart-card">
          <p class="stat-label">Batch ${batchLabel(n)}</p>
          <p class="stat-value">${frozen}/10</p>
          <p class="stat-note">${withJobs} with jobs · ${withAgents} with agents · ${status}</p>
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

  function renderAgents() {
    const empty = document.getElementById("agents-empty");
    const body = document.getElementById("agents-body");
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
        const completed = (row.solved || 0) + (row.valid_fail || 0);
        const stump = completed ? Math.round(((row.valid_fail || 0) / completed) * 1000) / 10 : "—";
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
          <td>${stump}${stump === "—" ? "" : "%"}</td>
        </tr>`;
      })
      .join("");

    const breakdown = document.getElementById("agent-task-breakdown");
    const agentTasks = tasks.filter(hasAgentJobs);
    breakdown.innerHTML = `<h2>By task</h2><p class="muted">Denominator is recorded Harbor trials for that model, not a padded ${PLANNED}. A 1-trial cheap probe shows 0/1, not 0/${PLANNED}. Infra and timeout are listed and excluded from stump.</p>
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
    const jobs = tasks.filter(hasJobs).length;
    const frozen = tasks.filter((task) => batchNum(task)).length;
    el.textContent = `${tasks.length} gallery packages · ${corpus.lab.inventory_size} inventory · ${frozen} frozen · ${jobs} with Harbor jobs · cheap plan k=${PLANNED}`;
  }

  function renderAll() {
    const surface = currentSurface();
    category = params().get("filter") || "all";
    renderNav();
    showSurface(surface);
    if (surface === "worlds") renderWorlds();
    if (surface === "coverage") renderCoverage();
    if (surface === "catalog") {
      renderTasksSub();
      renderChips();
      renderTable();
      const slug = currentSlug();
      renderPanel(slug ? bySlug.get(slug) : null);
    }
    if (surface === "runs") renderRuns();
    if (surface === "traces") renderTraces();
    if (surface === "stump") renderStump();
    if (surface === "failures") renderFailures();
    if (surface === "verifier") renderVerifier();
    if (surface === "harness") renderHarness();
    if (surface === "spend") renderSpend();
    if (surface === "batches") renderBatches();
    if (surface === "agents") renderAgents();
  }

  document.getElementById("nav-main").addEventListener("click", (event) => {
    const button = event.target.closest("[data-nav]");
    if (!button) return;
    const id = SURFACE_ALIASES[button.getAttribute("data-nav")] || button.getAttribute("data-nav");
    const keepSlug = id === "catalog" || id === "runs" || id === "traces" || id === "failures";
    setUrl({ surface: id, slug: keepSlug ? currentSlug() : "", push: true });
    renderAll();
  });

  document.querySelector(".brand").addEventListener("click", (event) => {
    event.preventDefault();
    setUrl({ surface: "worlds", slug: "", push: true });
    renderAll();
  });

  document.getElementById("later-close").addEventListener("click", () => {
    laterModal.hidden = true;
  });
  laterModal.addEventListener("click", (event) => {
    if (event.target === laterModal) laterModal.hidden = true;
  });

  document.getElementById("harbor-hub-btn").addEventListener("click", () => {
    laterBody.textContent =
      "Harbor Hub is disabled. Worlds Lab runs private Harbor 0.22 locally. This is not a published Harbor Hub dataset.";
    laterModal.hidden = false;
  });

  const prev = document.getElementById("preview-prev");
  const next = document.getElementById("preview-next");
  if (prev && next) {
    prev.addEventListener("click", () => {
      const n = (corpus.lab.instruction_previews || []).length || 1;
      previewIndex = (previewIndex + n - 1) % n;
      renderPreview();
    });
    next.addEventListener("click", () => {
      const n = (corpus.lab.instruction_previews || []).length || 1;
      previewIndex = (previewIndex + 1) % n;
      renderPreview();
    });
  }

  if (qEl) {
    qEl.addEventListener("input", () => {
      query = qEl.value.trim().toLowerCase();
      renderTable();
      const slug = currentSlug();
      if (slug) renderPanel(bySlug.get(slug) || null);
    });
  }

  window.addEventListener("popstate", () => renderAll());

  initTheme();
  renderAll();
  const initial = currentSlug();
  if (initial && currentSurface() === "catalog") selectTask(initial, false);
})();

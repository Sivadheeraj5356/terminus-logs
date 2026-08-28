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

  const SURFACE_ALIASES = {
    overview: "overview",
    worlds: "overview",
    coverage: "overview",
    tasks: "tasks",
    corpus: "tasks",
    agents: "agents",
    traces: "agents",
    verifier: "agents",
    stump: "agents",
    failures: "agents",
    harness: "agents",
  };

  const PLANNED = Number((corpus.lab.harness || {}).planned_attempts) || 8;
  const tasks = corpus.tasks;
  const bySlug = new Map(tasks.map((task) => [task.slug, task]));

  const rowsEl = document.getElementById("rows");
  const chipsEl = document.getElementById("chips");
  const shownEl = document.getElementById("shown");
  const qEl = document.getElementById("q");
  const panelTitle = document.getElementById("panel-title");
  const panelEmpty = document.getElementById("panel-empty");
  const panelBody = document.getElementById("panel-body");

  let category = "all";
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
    return currentSlug() ? "tasks" : "overview";
  }

  function setUrl({ slug, surface, push }) {
    const url = new URL(window.location.href);
    const nextSlug = slug === undefined ? currentSlug() : slug;
    const nextSurface = surface === undefined ? currentSurface() : surface;
    if (nextSlug) url.searchParams.set("task", nextSlug);
    else url.searchParams.delete("task");
    if (nextSurface && nextSurface !== "overview") url.searchParams.set("surface", nextSurface);
    else url.searchParams.delete("surface");
    history[push ? "pushState" : "replaceState"]({ task: nextSlug, surface: nextSurface }, "", url);
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

  function frontierComplete(task) {
    return agentModels(task).some((row) => (row.n || 0) >= PLANNED);
  }

  function shortModel(name) {
    const raw = String(name || "");
    if (/opus/i.test(raw)) return "Opus 5";
    if (/gpt-5\.6-sol/i.test(raw) || /gpt-5\.6/i.test(raw)) return "GPT-5.6-sol";
    return raw.replace(/^anthropic\//, "").replace(/^openai\//, "");
  }

  function matches(task) {
    if (category === "batch" && task.batch !== 1) return false;
    if (category === "measured" && !hasJobs(task)) return false;
    if (category === "agents" && !hasAgentJobs(task)) return false;
    if (
      category !== "all" &&
      category !== "batch" &&
      category !== "measured" &&
      category !== "agents" &&
      task.category !== category
    ) {
      return false;
    }
    if (!query) return true;
    const hay = [task.name, task.slug, task.category, categoryLabel(task.category), languages(task).join(" ")]
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function applyTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
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
    document.querySelectorAll("[data-nav]").forEach((el) => {
      const id = el.getAttribute("data-nav");
      if (id === "contributors" || id === "blog") {
        el.setAttribute("aria-current", "false");
        return;
      }
      if (el.tagName === "BUTTON" || el.tagName === "A") {
        el.setAttribute("aria-current", id === active ? "page" : "false");
      }
    });
  }

  function showSurface(id) {
    ["overview", "tasks", "agents"].forEach((sid) => {
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
        const recorded = row.n || 0;
        const cls = recorded >= PLANNED ? "chip-ok" : "chip-warn";
        return `<span class="chip ${cls}">${escapeHtml(shortModel(row.model))} ${row.solved || 0}/${PLANNED}</span>`;
      })
      .join(" ");
  }

  function renderChips() {
    const counts = corpus.lab.category_mix || {};
    const keys = ["all", "batch", "measured", "agents", ...Object.keys(CATEGORY_LABELS)];
    chipsEl.innerHTML = "";
    keys.forEach((key) => {
      const button = document.createElement("button");
      let label;
      if (key === "all") label = `All ${tasks.length}`;
      else if (key === "batch") label = `Batch 01 ${corpus.lab.batch_01_size || 10}`;
      else if (key === "measured") label = `Jobs ${corpus.lab.measured_size || 0}`;
      else if (key === "agents") label = `Agent trials ${tasks.filter(hasAgentJobs).length}`;
      else label = `${categoryLabel(key)} ${counts[key] || 0}`;
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", key === category ? "true" : "false");
      button.addEventListener("click", () => {
        category = key;
        renderChips();
        renderTable();
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
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}
          <span class="slug">${escapeHtml(task.slug)}</span>
        </td>
        <td><span class="chip cat-${escapeHtml(task.category)}">${escapeHtml(categoryLabel(task.category))}</span></td>
        <td>${langHtml || "—"}</td>
        <td>${task.batch === 1 ? `<span class="chip chip-batch">01</span>` : `<span class="muted">—</span>`}</td>
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
    shownEl.textContent = `${visible.length} of ${tasks.length}`;
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
    if (!task) {
      panelTitle.textContent = "Choose a row";
      panelEmpty.hidden = false;
      panelBody.hidden = true;
      panelBody.innerHTML = "";
      return;
    }
    panelEmpty.hidden = true;
    panelBody.hidden = false;
    panelTitle.textContent = task.name;
    const agents = agentModels(task);
    const oracle = oracleModels(task)[0];
    const roll = task.rollouts || {};
    const agentHtml = agents.length
      ? agents
          .map((row) => {
            const recorded = row.n || 0;
            return `<div>${escapeHtml(shortModel(row.model))}: ${row.solved || 0} solved · ${
              row.valid_fail || 0
            } valid fail · ${row.infra_error || 0} infra · ${
              row.timeout || 0
            } timeout · ${recorded}/${PLANNED} recorded</div>`;
          })
          .join("")
      : `<span class="muted">No terminus-2 trials ingested.</span>`;
    panelBody.innerHTML = `
      <p>${escapeHtml(task.summary || "")}</p>
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
          <span class="chip chip-ok">${task.has_oracle ? "oracle" : "no oracle"}</span>
          <span class="chip chip-ok">${task.has_tests ? "tests" : "no tests"}</span>
        </dd>
        <dt>Batch</dt>
        <dd>${task.batch === 1 ? "01 selected" : "gallery only"}</dd>
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
        const cell = (cov.cells || {})[`${domain}|${lang}`] || { gallery: 0, selected: 0, measured: 0 };
        if (!cell.gallery) {
          html += "<td class='empty-cell'></td>";
          return;
        }
        const cls = cell.measured ? "cell-measured" : cell.selected ? "cell-selected" : "";
        html += `<td class="${cls}">${cell.gallery}${
          cell.selected ? ` <span class="batch-mark">01</span>` : ""
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
    svg.innerHTML = `
      <polyline fill="rgba(123,108,240,0.16)" stroke="none" points="${area}"></polyline>
      <polyline fill="none" stroke="#7b6cf0" stroke-width="2" points="${pts}"></polyline>
    `;
  }

  function renderPreview() {
    const previews = corpus.lab.instruction_previews || [];
    const code = document.getElementById("preview-code");
    const meta = document.getElementById("preview-meta");
    const pager = document.getElementById("preview-pager");
    const dots = document.getElementById("preview-dots");
    if (!previews.length) {
      code.textContent = "No instruction previews in corpus.";
      return;
    }
    const item = previews[previewIndex % previews.length];
    meta.textContent = `${item.chars} chars · ${item.slug}`;
    code.innerHTML = (item.lines || [])
      .map((line) => `<span class="ln">${line.n}</span> ${escapeHtml(line.text || "")}`)
      .join("\n");
    if (previews.length > 1) {
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

  function renderOverview() {
    const jobs = tasks.filter(hasJobs).length;
    const frontier = tasks.filter(frontierComplete).length;
    const agentN = tasks.filter(hasAgentJobs).length;
    document.getElementById("stat-packages").textContent = String(corpus.lab.mvp_size || tasks.length);
    document.getElementById("stat-inventory").textContent = String(corpus.lab.inventory_size || 448);
    document.getElementById("stat-batch").textContent = String(corpus.lab.batch_01_size || 10);
    document.getElementById("stat-measured").textContent = `${jobs} → ${frontier}`;
    document.getElementById("stat-measured-note").textContent =
      `${jobs} with Harbor jobs (mostly oracle) · ${agentN} with agent trials · ${frontier} with a completed ${PLANNED}/${PLANNED} group`;

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
    renderCoverage();
    renderPreview();
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
    summary.innerHTML = rows
      .map((row, i) => {
        const planned = (corpus.lab.batch_01_size || 10) * PLANNED;
        const pct = Math.min(100, Math.round((row.n / Math.max(planned, 1)) * 100));
        return `<div class="model-line"><span class="dot" style="background:${
          i ? "#e08a4a" : "#3d9b6e"
        }"></span><strong>${escapeHtml(shortModel(row.model))}</strong>
          <span>${row.solved} solved / ${row.n} recorded on ${row.tasks} task${row.tasks === 1 ? "" : "s"}
          (plan ${planned} = 10×${PLANNED})
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
          <td>${row.n} <span class="muted">see n/${PLANNED} by task</span></td>
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
    breakdown.innerHTML = `<h2>By task</h2><p class="muted">n/8 is recorded attempts vs the planned 8. Infra and timeout are listed and excluded from stump.</p>
      <div class="table-card"><div class="table-scroll"><table>
        <thead><tr><th>Task</th><th>Model</th><th>Recorded / 8</th><th>Solved</th><th>Valid fail</th><th>Infra</th><th>Timeout</th></tr></thead>
        <tbody>${agentTasks
          .flatMap((task) =>
            agentModels(task).map(
              (row) => `<tr>
                <td class="name">${escapeHtml(task.name)}<span class="slug">${escapeHtml(task.slug)}</span></td>
                <td>${escapeHtml(shortModel(row.model))}</td>
                <td>${row.n || 0}/${PLANNED}</td>
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
    const frontier = tasks.filter(frontierComplete).length;
    el.innerHTML = `${tasks.length} public gallery packages (${corpus.lab.inventory_size} inventory). Batch 01 = ${
      corpus.lab.batch_01_size
    }. Harbor jobs ingested = ${jobs}. Completed ${PLANNED}/${PLANNED} frontier groups = ${frontier}.`;
  }

  function renderAll() {
    const surface = currentSurface();
    renderNav();
    showSurface(surface);
    if (surface === "overview") renderOverview();
    if (surface === "tasks") {
      renderTasksSub();
      renderChips();
      renderTable();
      const slug = currentSlug();
      renderPanel(slug ? bySlug.get(slug) : null);
    }
    if (surface === "agents") renderAgents();
  }

  function openLater(kind) {
    laterBody.textContent =
      kind === "blog"
        ? "No blog yet. Applied Work will publish later at appliedwork.ai. This control is a placeholder so the chrome matches a research-lab layout without inventing posts."
        : "Contributors listing comes later. This lab is Applied Work Worlds Lab in terminus-logs — not a public dataset hub.";
    laterModal.hidden = false;
  }

  document.getElementById("nav-main").addEventListener("click", (event) => {
    const button = event.target.closest("[data-nav]");
    if (!button) return;
    const id = button.getAttribute("data-nav");
    if (id === "contributors" || id === "blog") {
      openLater(id);
      return;
    }
    setUrl({ surface: id, slug: id === "tasks" ? currentSlug() : "", push: true });
    renderAll();
  });

  document.querySelector(".brand").addEventListener("click", (event) => {
    event.preventDefault();
    setUrl({ surface: "overview", slug: "", push: true });
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

  qEl.addEventListener("input", () => {
    query = qEl.value.trim().toLowerCase();
    renderTable();
  });

  window.addEventListener("popstate", () => renderAll());

  initTheme();
  renderAll();
  const initial = currentSlug();
  if (initial && currentSurface() === "tasks") selectTask(initial, false);
})();

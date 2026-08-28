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

  const SURFACES = [
    ["worlds", "Worlds"],
    ["coverage", "Coverage"],
    ["corpus", "Corpus"],
    ["traces", "Traces"],
    ["verifier", "Verifier"],
    ["stump", "Stump"],
    ["failures", "Failure map"],
    ["harness", "Harness"],
  ];

  const rowsEl = document.getElementById("rows");
  const chipsEl = document.getElementById("chips");
  const shownEl = document.getElementById("shown");
  const qEl = document.getElementById("q");
  const panelTitle = document.getElementById("panel-title");
  const panelEmpty = document.getElementById("panel-empty");
  const panelBody = document.getElementById("panel-body");
  const navEl = document.getElementById("surface-nav");
  const factMeasured = document.getElementById("fact-measured");

  const tasks = corpus.tasks;
  const bySlug = new Map(tasks.map((task) => [task.slug, task]));
  let category = "all";
  let query = "";

  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value;
  }

  function languages(task) {
    return (task.languages || []).join(", ") || "—";
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
    return params().get("surface") || "corpus";
  }

  function setUrl({ slug, surface, push }) {
    const url = new URL(window.location.href);
    const nextSlug = slug === undefined ? currentSlug() : slug;
    const nextSurface = surface === undefined ? currentSurface() : surface;
    if (nextSlug) url.searchParams.set("task", nextSlug);
    else url.searchParams.delete("task");
    if (nextSurface && nextSurface !== "corpus") url.searchParams.set("surface", nextSurface);
    else url.searchParams.delete("surface");
    history[push ? "pushState" : "replaceState"]({ task: nextSlug, surface: nextSurface }, "", url);
  }

  function measured(task) {
    return Boolean(task.measured) || (task.rollouts && task.rollouts.status === "measured");
  }

  function matches(task) {
    if (category === "batch" && task.batch !== 1) return false;
    if (category === "measured" && !measured(task)) return false;
    if (category !== "all" && category !== "batch" && category !== "measured" && task.category !== category) {
      return false;
    }
    if (!query) return true;
    const hay = [task.name, task.slug, task.category, categoryLabel(task.category), languages(task)]
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function visibleTasks() {
    return tasks.filter(matches);
  }

  function renderFacts() {
    const n = (corpus.lab && corpus.lab.measured_size) || tasks.filter(measured).length;
    if (factMeasured) factMeasured.textContent = String(n);
  }

  function renderNav() {
    const active = currentSurface();
    navEl.innerHTML = "";
    SURFACES.forEach(([id, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", id === active ? "true" : "false");
      button.addEventListener("click", () => {
        setUrl({ surface: id, push: true });
        renderAll();
      });
      navEl.appendChild(button);
    });
  }

  function showSurface(id) {
    SURFACES.forEach(([sid]) => {
      const el = document.getElementById(sid === "corpus" ? "gallery" : `surface-${sid}`);
      if (el) el.hidden = sid !== id;
    });
    document.getElementById("panel").hidden = id !== "corpus";
  }

  function renderChips() {
    const counts = corpus.lab.category_mix || {};
    const keys = ["all", "batch", "measured", ...Object.keys(CATEGORY_LABELS)];
    chipsEl.innerHTML = "";
    keys.forEach((key) => {
      const button = document.createElement("button");
      let label;
      if (key === "all") label = `All ${tasks.length}`;
      else if (key === "batch") label = `Batch 01 ${corpus.lab.batch_01_size || 10}`;
      else if (key === "measured") label = `Measured ${corpus.lab.measured_size || 0}`;
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

  function measuredCell(task) {
    if (!measured(task)) return `<span class="muted">—</span>`;
    const roll = task.rollouts || {};
    return `<span class="badge badge-ok">${escapeHtml(roll.label || "measured")}</span>`;
  }

  function renderTable() {
    const selected = currentSlug();
    const visible = visibleTasks();
    rowsEl.innerHTML = "";
    visible.forEach((task) => {
      const tr = document.createElement("tr");
      tr.dataset.slug = task.slug;
      tr.setAttribute("aria-selected", task.slug === selected ? "true" : "false");
      tr.tabIndex = 0;
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}${
          task.batch === 1 ? ` <span class="batch-mark">01</span>` : ""
        }</td>
        <td class="cat">${escapeHtml(categoryLabel(task.category))}</td>
        <td class="langs">${escapeHtml(languages(task))}</td>
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
    if (!measured(task) || task.stump_pct === null || task.stump_pct === undefined) return "—";
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
    const roll = task.rollouts || { label: "not run", note: "" };
    const rollClass = measured(task) ? "badge-ok" : "badge-warn";
    panelBody.innerHTML = `
      <p>${escapeHtml(task.summary || "")}</p>
      <dl class="meta">
        <dt>Category</dt>
        <dd>${escapeHtml(categoryLabel(task.category))}</dd>
        <dt>Difficulty</dt>
        <dd>${escapeHtml(task.difficulty)} <span class="muted">(author label)</span></dd>
        <dt>Languages</dt>
        <dd>${escapeHtml(languages(task))}</dd>
        <dt>UUID</dt>
        <dd class="mono">${escapeHtml(task.uuid)}</dd>
        <dt>Slug</dt>
        <dd class="mono">${escapeHtml(task.slug)}</dd>
        <dt>Oracle / tests</dt>
        <dd>
          <span class="badge badge-ok">${task.has_oracle ? "oracle" : "no oracle"}</span>
          <span class="badge badge-ok">${task.has_tests ? "tests" : "no tests"}</span>
        </dd>
        <dt>Batch</dt>
        <dd>${task.batch === 1 ? "01 selected" : "gallery only"}</dd>
        <dt>Rollouts</dt>
        <dd><span class="badge ${rollClass}">${escapeHtml(roll.label || "not run")}</span></dd>
        <dt>Stump %</dt>
        <dd>${escapeHtml(stumpDisplay(task))}</dd>
      </dl>
      <p class="muted">${escapeHtml(roll.note || "")}</p>
      <h3>Harbor files</h3>
      <ul class="files">${fileList(task)}</ul>
    `;
  }

  function selectTask(slug, push) {
    const task = bySlug.get(slug);
    if (!task) {
      renderPanel(null);
      panelTitle.textContent = "Unknown package";
      panelEmpty.hidden = false;
      panelEmpty.textContent = `No lab row for ?task=${slug}`;
      setUrl({ slug, push });
      renderTable();
      return;
    }
    setUrl({ slug, surface: "corpus", push });
    showSurface("corpus");
    renderNav();
    renderTable();
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
        }${cell.measured ? ` <span class="badge badge-ok">m</span>` : ""}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody>";
    table.innerHTML = html;
  }

  function measuredTasks() {
    return tasks.filter(measured);
  }

  function renderTraces() {
    const empty = document.getElementById("traces-empty");
    const body = document.getElementById("traces-body");
    const rows = measuredTasks();
    if (!rows.length) {
      empty.hidden = false;
      body.innerHTML = "";
      return;
    }
    empty.hidden = true;
    body.innerHTML = rows
      .map((task) => {
        const trials = (task.rollouts && task.rollouts.trials) || [];
        const items = trials
          .map(
            (trial) =>
              `<li><span class="mono">${escapeHtml(trial.model || "")}</span> · ${escapeHtml(
                trial.classification || ""
              )} — ${escapeHtml(trial.summary || "")}</li>`
          )
          .join("");
        return `<article><h3>${escapeHtml(task.name)}</h3><ul>${items || "<li>No trajectory summary.</li>"}</ul></article>`;
      })
      .join("");
  }

  function renderVerifier() {
    const body = document.getElementById("verifier-body");
    const rows = tasks.filter((t) => t.batch === 1);
    if (!rows.length) {
      body.innerHTML = "<p class='muted'>Batch 01 is not attached to the corpus.</p>";
      return;
    }
    body.innerHTML =
      "<ul>" +
      rows
        .map((task) => {
          const roll = task.rollouts || {};
          const status = measured(task) ? roll.label : "oracle / agents not ingested";
          return `<li><span class="mono">${escapeHtml(task.slug)}</span> — ${escapeHtml(status)}; timeout ${
            roll.timeout || 0
          }; infra ${roll.infra_error || 0}</li>`;
        })
        .join("") +
      "</ul>";
  }

  function renderStump() {
    const body = document.getElementById("stump-body");
    const rows = measuredTasks().filter((t) => t.stump_pct !== null && t.stump_pct !== undefined);
    if (!rows.length) {
      body.innerHTML =
        "<p class='muted'>No completed trials yet. Timeout and infra runs are not stumps.</p>";
      return;
    }
    body.innerHTML =
      "<ul>" +
      rows
        .map((task) => {
          const roll = task.rollouts || {};
          return `<li>${escapeHtml(task.name)} — ${task.stump_pct}% (${roll.valid_fail || 0}/${
            roll.completed_trials || 0
          } valid fail)</li>`;
        })
        .join("") +
      "</ul>";
  }

  function renderFailures() {
    const body = document.getElementById("failures-body");
    const rows = measuredTasks();
    if (!rows.length) {
      body.innerHTML = "<p class='muted'>No traces to taxonomize yet.</p>";
      return;
    }
    body.innerHTML =
      "<ul>" +
      rows
        .map((task) => {
          const fails = ((task.rollouts && task.rollouts.trials) || []).filter(
            (t) => t.classification === "valid_fail"
          );
          return `<li>${escapeHtml(task.name)} — ${fails.length} valid-fail traces. Rubric not authored.</li>`;
        })
        .join("") +
      "</ul>";
  }

  function renderAll() {
    const surface = currentSurface();
    renderNav();
    renderFacts();
    showSurface(surface);
    if (surface === "corpus") {
      renderChips();
      renderTable();
      const slug = currentSlug();
      renderPanel(slug ? bySlug.get(slug) : null);
    }
    if (surface === "coverage") renderCoverage();
    if (surface === "traces") renderTraces();
    if (surface === "verifier") renderVerifier();
    if (surface === "stump") renderStump();
    if (surface === "failures") renderFailures();
  }

  qEl.addEventListener("input", () => {
    query = qEl.value.trim().toLowerCase();
    renderTable();
  });

  window.addEventListener("popstate", () => renderAll());

  renderAll();
  const initial = currentSlug();
  if (initial && currentSurface() === "corpus") selectTask(initial, false);
})();

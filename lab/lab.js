(() => {
  const corpus = window.AW_CORPUS;
  if (!corpus || !Array.isArray(corpus.tasks)) {
    document.getElementById("panel-empty").textContent =
      "Could not load the lab corpus. Serve this folder over HTTP or keep corpus.js next to index.html.";
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

  const rowsEl = document.getElementById("rows");
  const chipsEl = document.getElementById("chips");
  const shownEl = document.getElementById("shown");
  const qEl = document.getElementById("q");
  const panelTitle = document.getElementById("panel-title");
  const panelEmpty = document.getElementById("panel-empty");
  const panelBody = document.getElementById("panel-body");

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

  function matches(task) {
    if (category !== "all" && task.category !== category) return false;
    if (!query) return true;
    const hay = [task.name, task.slug, task.category, categoryLabel(task.category), languages(task)]
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function visibleTasks() {
    return tasks.filter(matches);
  }

  function currentSlug() {
    return new URLSearchParams(window.location.search).get("task") || "";
  }

  function setUrl(slug, push) {
    const url = new URL(window.location.href);
    if (slug) url.searchParams.set("task", slug);
    else url.searchParams.delete("task");
    const method = push ? "pushState" : "replaceState";
    history[method]({ task: slug }, "", url);
  }

  function renderChips() {
    const counts = corpus.lab.category_mix || {};
    const keys = ["all", ...Object.keys(CATEGORY_LABELS)];
    chipsEl.innerHTML = "";
    keys.forEach((key) => {
      const button = document.createElement("button");
      const label = key === "all" ? `All ${tasks.length}` : `${categoryLabel(key)} ${counts[key] || 0}`;
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
    const visible = visibleTasks();
    rowsEl.innerHTML = "";
    visible.forEach((task) => {
      const tr = document.createElement("tr");
      tr.dataset.slug = task.slug;
      tr.setAttribute("aria-selected", task.slug === selected ? "true" : "false");
      tr.tabIndex = 0;
      tr.innerHTML = `
        <td class="name">${escapeHtml(task.name)}</td>
        <td class="cat">${escapeHtml(categoryLabel(task.category))}</td>
        <td class="langs">${escapeHtml(languages(task))}</td>
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
        <dt>Rollouts</dt>
        <dd><span class="badge badge-warn">${escapeHtml(roll.label || "not run")}</span></dd>
        <dt>Stump %</dt>
        <dd>—</dd>
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
      setUrl(slug, push);
      renderTable();
      return;
    }
    setUrl(slug, push);
    renderTable();
    renderPanel(task);
    const row = rowsEl.querySelector(`[data-slug="${CSS.escape(slug)}"]`);
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  qEl.addEventListener("input", () => {
    query = qEl.value.trim().toLowerCase();
    renderTable();
  });

  window.addEventListener("popstate", () => {
    const slug = currentSlug();
    renderTable();
    renderPanel(slug ? bySlug.get(slug) : null);
  });

  renderChips();
  renderTable();
  const initial = currentSlug();
  if (initial) selectTask(initial, false);
})();

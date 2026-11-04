const API_BASE = "";
const $ = (id) => document.getElementById(id);
const HISTORY_KEY = "dis.inspection.history.v1";
const KEY_STORAGE = "dis.inspection.api_key";

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}
function saveHistory(items) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 30)));
}
function escapeText(value) { return String(value ?? ""); }
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = escapeText(text);
  return node;
}
function addList(parent, items, warning = false) {
  if (!items || !items.length) {
    parent.append(el("div", "empty-state", "No evidence found in this inspection."));
    return;
  }
  const list = el("ul", warning ? "report-list warning-list" : "report-list");
  items.forEach(item => list.append(el("li", "", item)));
  parent.append(list);
}
function addTags(parent, items, muted = false) {
  if (!items || !items.length) {
    parent.append(el("span", "summary-text", "No signals detected"));
    return;
  }
  const wrap = el("div", "tag-list");
  items.forEach(item => wrap.append(el("span", muted ? "tag muted" : "tag", item)));
  parent.append(wrap);
}
function card(title, content, full = false) {
  const node = el("article", full ? "report-card full" : "report-card");
  node.append(el("h3", "", title));
  if (content instanceof Node) node.append(content);
  return node;
}
function renderHistory() {
  const history = getHistory();
  $("stat-inspections").textContent = history.length;
  const targets = [$("overview-history"), $("full-history")];
  targets.forEach((target, index) => {
    target.replaceChildren();
    if (!history.length) {
      target.append(el("div", "empty-state", index ? "No inspections yet. Start by inspecting a GitHub repository." : "Your repository inspections will appear here."));
      return;
    }
    history.forEach((item) => {
      const row = el("div", "history-row");
      row.append(el("span", "history-symbol", "⌘"));
      const info = el("div", "history-info");
      info.append(el("b", "", item.repository));
      info.append(el("small", "", [item.ref, item.frameworks?.join(", ")].filter(Boolean).join(" · ")));
      row.append(info);
      row.append(el("time", "", new Date(item.createdAt).toLocaleString()));
      const button = el("button", "outline-button", "View report");
      button.type = "button";
      button.addEventListener("click", () => {
        if (item.report) {
          showReport(item.report);
          navigate("inspector");
        }
      });
      row.append(button);
      target.append(row);
    });
  });
}
function navigate(view) {
  document.querySelectorAll(".view").forEach(node => node.classList.toggle("active", node.id === "view-" + view));
  document.querySelectorAll(".nav-item").forEach(node => node.classList.toggle("active", node.dataset.view === view));
  $("breadcrumb-current").textContent = view === "inspector" ? "Repository inspector" : view === "visual" ? "Visual inspection" : view === "history" ? "Inspection history" : "Overview";
  if (location.hash !== "#" + view) history.replaceState(null, "", "#" + view);
}
document.querySelectorAll("[data-view], [data-go]").forEach(node => node.addEventListener("click", event => {
  event.preventDefault();
  navigate(node.dataset.view || node.dataset.go);
}));
function showReport(data) {
  const section = $("report-section");
  section.replaceChildren();
  section.classList.remove("hidden");
  const head = el("div", "report-head");
  const title = el("div");
  title.append(el("span", "eyebrow", "INSPECTION COMPLETE"));
  title.append(el("h2", "", data.repository));
  title.append(el("p", "", "Ref: " + data.ref + (data.description ? " · " + data.description : "")));
  head.append(title);
  const actions = el("div", "report-actions");
  const copy = el("button", "outline-button", "Copy report");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    copy.textContent = "Copied";
    setTimeout(() => copy.textContent = "Copy report", 1400);
  });
  actions.append(copy);
  head.append(actions);
  section.append(head);

  const stats = el("div", "report-stats");
  [[data.primary_language || "—", "PRIMARY LANGUAGE"], [data.inspected_file_count, "FILES SAMPLED"], [data.tree_entry_count, "TREE ENTRIES"], [data.ref || "—", "INSPECTED REF"]].forEach(([value, label]) => {
    const item = el("div", "report-stat");
    item.append(el("small", "", label), el("b", "", value));
    stats.append(item);
  });
  section.append(stats);

  const grid = el("div", "report-grid");
  grid.append(card("Architecture summary", el("p", "summary-text", data.architecture_summary), true));
  const stack = el("div");
  addTags(stack, data.detected_stacks);
  stack.append(el("h3", "", "Frameworks"));
  addTags(stack, data.frameworks, true);
  stack.append(el("h3", "", "Package managers"));
  addTags(stack, data.package_managers, true);
  grid.append(card("Technology landscape", stack));

  const routes = el("div");
  addList(routes, data.app_entry_points);
  routes.append(el("h3", "", "Routes and pages"));
  addList(routes, data.route_and_page_files);
  grid.append(card("Application structure", routes));

  const design = el("div");
  addList(design, data.design_system_evidence);
  design.append(el("h3", "", "Component and style files"));
  addList(design, data.component_and_style_files);
  grid.append(card("Design-system discovery", design));

  const commands = el("div");
  addList(commands, data.test_and_lint_commands);
  grid.append(card("Declared project commands", commands));

  const tableWrap = el("div");
  if (data.file_evidence?.length) {
    const table = el("table", "file-table");
    const thead = el("thead");
    const header = el("tr");
    ["FILE PATH", "CATEGORY", "BYTES"].forEach(label => header.append(el("th", "", label)));
    thead.append(header); table.append(thead);
    const tbody = el("tbody");
    data.file_evidence.forEach(file => {
      const tr = el("tr");
      tr.append(el("td", "", file.path), el("td", "", file.category), el("td", "", file.bytes_read + (file.truncated ? "+" : "")));
      tbody.append(tr);
    });
    table.append(tbody); tableWrap.append(table);
  } else addList(tableWrap, []);
  grid.append(card("Sampled file evidence", tableWrap, true));

  const limits = el("div");
  addList(limits, data.limitations, true);
  grid.append(card("Limitations and verification boundary", limits, true));
  section.append(grid);
  section.scrollIntoView({behavior:"smooth", block:"start"});
}
async function inspect(event) {
  event.preventDefault();
  $("form-error").textContent = "";
  $("report-section").classList.add("hidden");
  const repository = $("repository-input").value.trim();
  const ref = $("ref-input").value.trim();
  const button = $("inspect-submit");
  button.disabled = true;
  button.querySelector(".button-label").textContent = "Inspecting repository…";
  $("loading-panel").classList.remove("hidden");
  $("loading-message").textContent = "Reading repository metadata and file structure…";
  try {
    const payload = {repository, include_file_samples: $("sample-files").checked};
    if (ref) payload.ref = ref;
    const headers = {"Content-Type":"application/json"};
    const key = sessionStorage.getItem(KEY_STORAGE);
    if (key) headers["X-DIS-API-Key"] = key;
    const response = await fetch(API_BASE + "/api/v1/repositories/inspect", {
      method:"POST", headers, body:JSON.stringify(payload)
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 || response.status === 503) openSettings();
      throw new Error(body.detail || "Repository inspection failed (HTTP " + response.status + ").");
    }
    showReport(body);
    const history = getHistory();
    history.unshift({
      repository:body.repository, ref:body.ref, frameworks:body.frameworks,
      createdAt:new Date().toISOString(), report:body
    });
    saveHistory(history);
    renderHistory();
    $("loading-message").textContent = "Inspection completed.";
  } catch (error) {
    $("form-error").textContent = error.message || "Could not inspect this repository.";
  } finally {
    $("loading-panel").classList.add("hidden");
    button.disabled = false;
    button.querySelector(".button-label").textContent = "Inspect repository";
  }
}
$("inspect-form").addEventListener("submit", inspect);
async function loadSystemStatus() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Service unavailable");
    const data = await response.json();
    $("health-dot").className = "good";
    $("health-label").textContent = "DIS online";
    $("stat-health").textContent = "Online";
    $("stat-health-note").textContent = "API version " + data.version;
  } catch {
    $("health-dot").className = "bad";
    $("health-label").textContent = "Service unavailable";
    $("stat-health").textContent = "Offline";
    $("stat-health-note").textContent = "Unable to reach DIS API";
  }
  try {
    const response = await fetch("/api/v1/provider");
    const data = await response.json();
    $("stat-provider").textContent = data.configured ? data.provider : "Deterministic";
    $("stat-model").textContent = data.configured ? (data.model || "Model configured") : "LLM provider not configured";
  } catch {
    $("stat-provider").textContent = "Unavailable";
    $("stat-model").textContent = "Could not read provider status";
  }
}
function openSettings() {
  $("api-key-input").value = sessionStorage.getItem(KEY_STORAGE) || "";
  $("settings-dialog").showModal();
}
$("settings-open").addEventListener("click", openSettings);
$("settings-open-secondary").addEventListener("click", openSettings);
$("save-key").addEventListener("click", () => {
  const key = $("api-key-input").value.trim();
  if (key) sessionStorage.setItem(KEY_STORAGE, key);
  else sessionStorage.removeItem(KEY_STORAGE);
  $("settings-dialog").close();
});
$("clear-key").addEventListener("click", () => {
  sessionStorage.removeItem(KEY_STORAGE);
  $("api-key-input").value = "";
});
$("clear-history").addEventListener("click", () => {
  if (confirm("Clear inspection history saved in this browser?")) {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
  }
});
function renderVisualReport(data) {
  const section = $("visual-report");
  section.replaceChildren();
  section.classList.remove("hidden");
  const head = el("div", "report-head");
  const title = el("div");
  title.append(el("span", "eyebrow", "VISUAL INSPECTION COMPLETE"));
  title.append(el("h2", "", data.page_title || data.final_url));
  title.append(el("p", "", data.final_url + " · HTTP " + (data.status_code ?? "unknown")));
  head.append(title);
  const score = el("div", "visual-score");
  score.append(el("strong", "", data.score + "/100"), el("span", "", "Initial UI quality signal · Grade " + data.grade));
  head.append(score);
  section.append(head);

  const previews = el("div", "visual-previews");
  (data.viewports || []).forEach(viewport => {
    const figure = el("figure", "visual-preview");
    figure.append(el("figcaption", "", viewport.name + " · " + viewport.width + " × " + viewport.height));
    if (viewport.screenshot_base64) {
      const img = document.createElement("img");
      img.alt = "Captured " + viewport.name + " viewport";
      img.loading = "lazy";
      img.src = "data:image/jpeg;base64," + viewport.screenshot_base64;
      figure.append(img);
    } else figure.append(el("div", "empty-state", "Screenshot capture disabled"));
    previews.append(figure);
  });
  section.append(previews);

  const findingsTitle = el("div", "section-title");
  findingsTitle.append(el("h2", "", "Detected issues (" + (data.findings || []).length + ")"));
  section.append(findingsTitle);
  const findings = el("div", "visual-findings");
  (data.findings || []).forEach(finding => {
    const item = el("article", "visual-finding");
    const meta = el("div", "visual-finding-meta");
    meta.append(el("span", "tag", finding.category), el("span", "severity severity-" + finding.severity, finding.severity));
    item.append(meta, el("h3", "", finding.title), el("p", "", finding.description));
    item.append(el("small", "", "Evidence: " + finding.evidence));
    item.append(el("p", "visual-recommendation", "Recommendation: " + finding.recommendation));
    findings.append(item);
  });
  if (!(data.findings || []).length) findings.append(el("div", "empty-state", "No issues were detected by the current deterministic checks."));
  section.append(findings);
  const limits = el("div", "report-card full");
  limits.append(el("h3", "", "Analysis boundaries"));
  addList(limits, data.limitations, true);
  section.append(limits);
  section.scrollIntoView({behavior:"smooth", block:"start"});
}

async function inspectVisual(event) {
  event.preventDefault();
  $("visual-error").textContent = "";
  $("visual-report").classList.add("hidden");
  const button = $("visual-submit");
  button.disabled = true;
  button.querySelector(".button-label").textContent = "Inspecting application…";
  $("visual-loading").classList.remove("hidden");
  try {
    const headers = {"Content-Type":"application/json"};
    const key = sessionStorage.getItem(KEY_STORAGE);
    if (key) headers["X-DIS-API-Key"] = key;
    const response = await fetch(API_BASE + "/api/v1/visual/inspect", {
      method:"POST", headers,
      body:JSON.stringify({url:$("visual-url").value.trim(), capture_screenshots:true})
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 || response.status === 503) openSettings();
      throw new Error(body.detail || "Visual inspection failed (HTTP " + response.status + ").");
    }
    renderVisualReport(body);
  } catch (error) {
    $("visual-error").textContent = error.message || "Could not inspect this application.";
  } finally {
    $("visual-loading").classList.add("hidden");
    button.disabled = false;
    button.querySelector(".button-label").textContent = "Inspect application UI";
  }
}
$("visual-form").addEventListener("submit", inspectVisual);

const initial = location.hash.replace("#", "");
navigate(["overview","inspector","visual","history"].includes(initial) ? initial : "overview");
renderHistory();
loadSystemStatus();

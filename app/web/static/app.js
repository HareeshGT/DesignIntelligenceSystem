const API_BASE = "";
const $ = (id) => document.getElementById(id);
const HISTORY_KEY = "dis.inspection.history.v1";
const KEY_STORAGE = "dis.inspection.api_key";
let latestVisualReport = null;
let latestRepositoryReport = null;
let latestProposalToken = null;
function apiHeaders() {
  const headers = {"Content-Type":"application/json"};
  const key = sessionStorage.getItem(KEY_STORAGE);
  if (key) headers["X-DIS-API-Key"] = key;
  return headers;
}

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
  if (data.platform_profiles?.length) {
    const profiles = el("div");
    data.platform_profiles.forEach(profile => {
      profiles.append(el("h3", "", profile.name + " · " + profile.adapter_id));
      addList(profiles, profile.capabilities);
      addList(profiles, profile.limitations, true);
    });
    grid.append(card("Platform adapter capabilities", profiles, true));
  }

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
  if (data.visual_summary) section.append(el("p", "visual-summary", data.visual_summary));
  if (data.design_system_signals && Object.keys(data.design_system_signals).length) {
    const tokens = el("div", "design-signals");
    Object.entries(data.design_system_signals).forEach(([key, values]) => {
      const block = el("div", "design-signal");
      block.append(el("b", "", key.replaceAll("_", " ")));
      (values || []).forEach(value => block.append(el("span", "tag muted", value)));
      tokens.append(block);
    });
    section.append(tokens);
  }
  if (data.inspected_pages?.length) {
    const routes = el("div", "report-card full");
    routes.append(el("h3", "", "Pages inspected (" + data.inspected_pages.length + ")"));
    addList(routes, data.inspected_pages.map(page => page.url + " · " + (page.status_code ?? "unavailable") + " · " + page.title));
    section.append(routes);
  }

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
    const visualRequest = fetch(API_BASE + "/api/v1/visual/inspect", {
      method:"POST", headers:apiHeaders(),
      body:JSON.stringify({
        url:$("visual-url").value.trim(), capture_screenshots:true,
        crawl_internal_routes:$("crawl-routes").checked, max_routes:4, analyze_with_vision:$("vision-analysis").checked
      })
    }).then(async response => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401 || response.status === 503) openSettings();
        throw new Error(body.detail || "Visual inspection failed (HTTP " + response.status + ").");
      }
      return body;
    });
    const repositoryValue = $("visual-repository").value.trim();
    const repositoryRequest = repositoryValue ? fetch(API_BASE + "/api/v1/repositories/inspect", {
      method:"POST", headers:apiHeaders(),
      body:JSON.stringify({repository:repositoryValue, ref:$("visual-ref").value.trim() || null, include_file_samples:true})
    }).then(async response => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401 || response.status === 503) openSettings();
        throw new Error(body.detail || "Repository inspection failed (HTTP " + response.status + ").");
      }
      return body;
    }) : Promise.resolve(null);
    const [body, repositoryReport] = await Promise.all([visualRequest, repositoryRequest]);
    latestVisualReport = body;
    latestRepositoryReport = repositoryReport;
    if (repositoryReport) {
      $("improvement-repo").value = repositoryReport.repository;
      $("improvement-ref").value = repositoryReport.ref;
      const suggested = [...(repositoryReport.component_and_style_files || []), ...(repositoryReport.app_entry_points || [])]
        .filter(path => /\.(tsx|jsx|ts|js|vue|svelte|html|css|scss|dart|swift|kt|kts|qml|ui|m|mm)$/i.test(path))
        .slice(0,4);
      if (!$("improvement-files").value.trim() && suggested.length) $("improvement-files").value = suggested.join(", ");
    }
    renderVisualReport(body);
    if (repositoryReport) {
      const context = el("div", "report-card full");
      context.append(el("h3", "", "Linked repository context: " + repositoryReport.repository));
      context.append(el("p", "summary-text", repositoryReport.architecture_summary));
      const list = el("div");
      addList(list, repositoryReport.frameworks);
      context.append(list);
      $("visual-report").append(context);
    }
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

async function compareVersions(event) {
  event.preventDefault();
  $("compare-error").textContent = "";
  $("compare-submit").disabled = true;
  $("compare-submit").textContent = "Comparing screenshots…";
  try {
    const response = await fetch("/api/v1/visual/compare", {
      method:"POST", headers:apiHeaders(),
      body:JSON.stringify({baseline_url:$("baseline-url").value.trim(), candidate_url:$("candidate-url").value.trim()})
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Visual comparison failed.");
    const report = $("compare-report");
    report.replaceChildren();
    report.classList.remove("hidden");
    report.append(el("h3", "", "Before / after comparison"));
    (body.comparisons || []).forEach(item => {
      const row = el("div", "comparison-row");
      row.append(el("b", "", item.viewport), el("span", "", item.pixel_similarity_percent + "% pixel similarity"), el("span", "", item.changed_pixel_percent + "% pixels changed"));
      report.append(row);
      const pair = el("div", "comparison-images");
      [["Before", item.baseline_screenshot_base64], ["After", item.candidate_screenshot_base64]].forEach(([label, imageData]) => {
        const figure = el("figure", "comparison-image");
        figure.append(el("figcaption", "", label + " · " + item.viewport));
        const image = document.createElement("img");
        image.alt = label + " " + item.viewport + " screenshot";
        image.src = "data:image/jpeg;base64," + imageData;
        figure.append(image);
        pair.append(figure);
      });
      report.append(pair);
    });
    report.append(el("p", "summary-text", "Finding score change: " + (body.score_delta > 0 ? "+" : "") + body.score_delta));
    const resolved = el("div");
    resolved.append(el("h4", "", "Resolved findings"));
    addList(resolved, body.resolved_finding_titles);
    report.append(resolved);
    const added = el("div");
    added.append(el("h4", "", "New findings"));
    addList(added, body.new_finding_titles);
    report.append(added);
    report.append(el("p", "privacy-caption", (body.limitations || []).join(" ")));
  } catch (error) {
    $("compare-error").textContent = error.message || "Could not compare the two versions.";
  } finally {
    $("compare-submit").disabled = false;
    $("compare-submit").textContent = "Compare versions →";
  }
}
$("compare-form").addEventListener("submit", compareVersions);

async function proposeImprovement(event) {
  event.preventDefault();
  $("improvement-error").textContent = "";
  if (!latestVisualReport) {
    $("improvement-error").textContent = "Run a visual inspection first so the proposal can use real findings.";
    return;
  }
  if (!$("source-consent").checked) {
    $("improvement-error").textContent = "Confirm consent before sending selected source files to the configured model provider.";
    return;
  }
  const paths = $("improvement-files").value.split(",").map(value => value.trim()).filter(Boolean);
  if (!paths.length || paths.length > 4) {
    $("improvement-error").textContent = "Provide between one and four existing frontend source paths.";
    return;
  }
  const button = $("propose-submit");
  button.disabled = true;
  button.textContent = "Preparing patch proposal…";
  try {
    const response = await fetch("/api/v1/improvements/propose", {
      method:"POST", headers:apiHeaders(),
      body:JSON.stringify({
        repository:$("improvement-repo").value.trim(),
        ref:$("improvement-ref").value.trim() || null,
        target_files:paths,
        findings:(latestVisualReport.findings || []).slice(0,20),
        visual_summary:latestVisualReport.visual_summary || ""
      })
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Could not generate the improvement proposal.");
    latestProposalToken = body.proposal_token;
    const panel = $("proposal-report");
    panel.replaceChildren();
    panel.classList.remove("hidden");
    panel.append(el("h3", "", body.summary));
    panel.append(el("p", "privacy-caption", "Files: " + (body.files || []).map(file => file.path).join(", ") + " · Expires in 30 minutes"));
    panel.append(el("pre", "proposal-diff", body.diff || "No diff supplied."));
    const approval = el("label", "approval-check");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.id = "approve-patch";
    approval.append(check, el("span", "", "I reviewed this diff and approve creating a GitHub pull request."));
    panel.append(approval);
    const apply = el("button", "primary-button", "Approve and create pull request →");
    apply.type = "button";
    apply.disabled = true;
    check.addEventListener("change", () => apply.disabled = !check.checked);
    apply.addEventListener("click", async () => {
      if (!check.checked || !latestProposalToken) return;
      apply.disabled = true;
      apply.textContent = "Creating pull request…";
      try {
        const result = await fetch("/api/v1/improvements/apply", {
          method:"POST", headers:apiHeaders(),
          body:JSON.stringify({proposal_token:latestProposalToken, approval:true})
        });
        const outcome = await result.json().catch(() => ({}));
        if (!result.ok) throw new Error(outcome.detail || "Could not create the pull request.");
        const link = document.createElement("a");
        link.href = outcome.pull_request_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "Open generated pull request #" + outcome.number;
        link.className = "proposal-link";
        panel.append(link);
        latestProposalToken = null;
      } catch (error) {
        $("improvement-error").textContent = error.message || "Apply failed.";
        apply.disabled = false;
      }
    });
    panel.append(apply);
  } catch (error) {
    $("improvement-error").textContent = error.message || "Could not generate a proposal.";
  } finally {
    button.disabled = false;
    button.textContent = "Generate improvement proposal →";
  }
}
$("improvement-form").addEventListener("submit", proposeImprovement);

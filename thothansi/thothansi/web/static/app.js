// Thothansi dashboard — vanilla JS, talks to the FastAPI JSON API.
const $ = (id) => document.getElementById(id);
const api = (path, opts) => fetch(path, opts).then((r) => {
  if (!r.ok) return r.json().then((e) => Promise.reject(e)).catch(() => Promise.reject({ detail: r.statusText }));
  return r.json();
});

const SEVS = ["critical", "high", "medium", "low", "info"];
const GLYPH = { modern: "◆", mythic: "𓂀" };
let lastRunId = null;

// ---- theme ----------------------------------------------------------------
function setTheme(name) {
  document.documentElement.setAttribute("data-theme", name);
  $("brandGlyph").textContent = GLYPH[name] || "◆";
  document.querySelectorAll("#themeSwitch button").forEach((b) =>
    b.setAttribute("aria-pressed", b.dataset.themeName === name ? "true" : "false")
  );
}
$("themeSwitch").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (btn) setTheme(btn.dataset.themeName);
});

// ---- state / scope / providers -------------------------------------------
async function loadState() {
  const s = await api("/api/state");
  setTheme(s.theme);
  const sel = $("providerSelect");
  sel.innerHTML = "";
  s.providers.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = `${p.label} (${p.model})${p.configured ? "" : " — not configured"}`;
    if (p.active) opt.selected = true;
    sel.appendChild(opt);
  });
  const list = $("providerList");
  list.innerHTML = "";
  s.providers.forEach((p) => {
    const row = document.createElement("div");
    row.className = "prov" + (p.active ? " active" : "");
    row.innerHTML = `<span><span class="dot ${p.configured ? "on" : "off"}"></span>${p.label}</span>
      <span class="meta">${p.local ? "local" : "remote"} · ${p.model}</span>`;
    list.appendChild(row);
  });
}

async function loadScope() {
  const s = await api("/api/scope");
  $("engagement").textContent = s.engagement + (s.authorized_by ? ` · authorized by ${s.authorized_by}` : "");
  const ul = $("scopeList");
  ul.innerHTML = "";
  if (!s.entries.length) {
    ul.innerHTML = '<li class="scope-empty" style="border:none">Scope is empty — add a target or edit config/scope.yaml</li>';
    return;
  }
  s.entries.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = e;
    ul.appendChild(li);
  });
}

$("scopeAdd").addEventListener("click", async () => {
  const v = $("scopeInput").value.trim();
  if (!v) return;
  try {
    await api("/api/scope", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: v }),
    });
    $("scopeInput").value = "";
    loadScope();
  } catch (e) {
    alert("Could not add to scope: " + (e.detail || e.error || "error"));
  }
});
$("scopeInput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("scopeAdd").click(); });

// ---- run history ----------------------------------------------------------
async function loadHistory() {
  const runs = await api("/api/runs");
  const ul = $("runHistory");
  if (!runs.length) { ul.innerHTML = '<li class="scope-empty" style="border:none">No saved runs yet.</li>'; return; }
  ul.innerHTML = "";
  runs.slice(0, 12).forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `<a data-run="${r.id}">${r.id}</a> <span class="muted">· ${r.targets.join(", ")} · ${r.findings} findings</span>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll("a[data-run]").forEach((a) =>
    a.addEventListener("click", () => openRun(a.dataset.run)));
}

// ---- run ------------------------------------------------------------------
$("runBtn").addEventListener("click", async () => {
  const targets = $("targets").value.split("\n").map((t) => t.trim()).filter(Boolean);
  if (!targets.length) { alert("Enter at least one target."); return; }
  const log = $("log");
  log.style.display = "block";
  log.innerHTML = '<div><span class="spinner"></span> running pipeline…</div>';
  $("runBtn").disabled = true;
  try {
    const res = await api("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        targets,
        do_triage: $("doTriage").checked,
        provider: $("providerSelect").value,
      }),
    });
    log.innerHTML = "";
    if (res.refused && res.refused.length)
      appendLog("scope", "⛔ refused (out of scope): " + res.refused.join(", "));
    (res.events || []).forEach((e) => appendLog(e.stage, e.msg));
    lastRunId = res.run_id;
    renderResults(res);
    loadHistory();
  } catch (e) {
    log.innerHTML = "";
    appendLog("error", e.detail ? JSON.stringify(e.detail) : (e.error || "run failed"));
  } finally {
    $("runBtn").disabled = false;
  }
});

function appendLog(stage, msg) {
  const d = document.createElement("div");
  d.innerHTML = `<span class="stage">[${stage}]</span> ${escapeHtml(msg)}`;
  $("log").appendChild(d);
  $("log").scrollTop = $("log").scrollHeight;
}

async function openRun(id) {
  const res = await api("/api/runs/" + id);
  lastRunId = id;
  renderResults(res);
  window.scrollTo({ top: $("resultsCard").offsetTop - 20, behavior: "smooth" });
}

function renderResults(res) {
  $("resultsCard").style.display = "block";
  $("runLabel").textContent = "· " + (res.run_id || lastRunId || "");
  renderLedger(res.severity_counts || {});
  renderFindings(res.findings || []);
  renderAssets(res.assets || [], res.asset_counts || {});
}

function renderLedger(counts) {
  const total = Math.max(1, SEVS.reduce((a, s) => a + (counts[s] || 0), 0));
  $("ledger").innerHTML = SEVS.map((s) => {
    const c = counts[s] || 0;
    const pct = Math.round((c / total) * 100);
    return `<div class="band">
      <span class="name sev-${s}">${s}</span>
      <span class="bar"><span class="fill-${s}" style="width:${c ? Math.max(pct, 4) : 0}%"></span></span>
      <span class="count">${c}</span></div>`;
  }).join("");
}

function renderFindings(findings) {
  const el = $("tab-findings");
  if (!findings.length) { el.innerHTML = '<p class="muted">No findings recorded.</p>'; return; }
  el.innerHTML = findings.map((f) => {
    const sev = f.triage_severity || f.severity;
    const adjusted = f.triage_severity && f.triage_severity !== f.severity;
    const note = [];
    if (f.triage_rationale) note.push(`<b>Analyst note.</b> ${escapeHtml(f.triage_rationale)}`);
    if (f.triage_recommendation) note.push(`<b>Next step.</b> ${escapeHtml(f.triage_recommendation)}`);
    return `<div class="finding s-${sev}">
      <div class="head">
        <span class="tag sev-${sev}">${sev}</span>
        <span class="title">${escapeHtml(f.title)}</span>
        ${f.asset ? `<span class="asset">${escapeHtml(f.asset)}</span>` : ""}
      </div>
      ${f.description ? `<p class="desc">${escapeHtml(f.description)}</p>` : ""}
      ${adjusted ? `<p class="muted" style="font-size:12px;margin:6px 0 0;">severity ${f.severity} → ${sev} (AI-adjusted)</p>` : ""}
      ${note.length ? `<div class="note">${note.join("<br>")}</div>` : ""}
    </div>`;
  }).join("");
}

function renderAssets(assets, counts) {
  const el = $("tab-assets");
  const summary = Object.entries(counts).map(([k, v]) => `${k}: ${v}`).join(" · ");
  if (!assets.length) { el.innerHTML = '<p class="muted">No assets discovered.</p>'; return; }
  el.innerHTML = `<p class="muted" style="margin-top:0">${summary}</p><div class="asset-grid">` +
    assets.map((a) => `<div class="asset-chip"><span class="t">${a.type}</span> ${escapeHtml(a.value)}</div>`).join("") +
    `</div>`;
}

document.querySelectorAll(".tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", "false"));
    b.setAttribute("aria-selected", "true");
    $("tab-findings").style.display = b.dataset.tab === "findings" ? "block" : "none";
    $("tab-assets").style.display = b.dataset.tab === "assets" ? "block" : "none";
  }));

$("reportBtn").addEventListener("click", () => {
  if (lastRunId) window.open("/api/report/" + lastRunId, "_blank");
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// init
loadState().catch(() => {});
loadScope().catch(() => {});
loadHistory().catch(() => {});

let engagementId = null;

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}
function theme() {
  return document.querySelector('input[name="theme"]:checked').value;
}
function setOutput(data) {
  document.getElementById('output').textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

document.querySelectorAll('input[name="theme"]').forEach((el) => {
  el.addEventListener('change', () => document.documentElement.setAttribute('data-theme', theme()));
});

async function createEngagement() {
  const payload = {
    name: document.getElementById('engagementName').value,
    scope: [document.getElementById('scope').value],
    authorization_statement: document.getElementById('authz').value,
    mode: mode(),
    theme: theme(),
    provider: 'local-rule-based'
  };
  const response = await fetch('/engagements', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) { setOutput(data); return; }
  engagementId = data.id;
  document.getElementById('engagementStatus').textContent = `Created engagement ${data.id}`;
  setOutput(data);
}

async function importArtifact() {
  if (!engagementId) { setOutput('Create an engagement first.'); return; }
  const payload = {
    source_type: document.getElementById('sourceType').value,
    name: document.getElementById('artifactName').value,
    content: document.getElementById('artifactContent').value
  };
  const response = await fetch(`/engagements/${engagementId}/imports`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  setOutput(await response.json());
}

async function planWorkflow() {
  if (!engagementId) { setOutput('Create an engagement first.'); return; }
  const response = await fetch(`/engagements/${engagementId}/plan`, {method: 'POST'});
  setOutput(await response.json());
}

async function runWorkflow() {
  if (!engagementId) { setOutput('Create an engagement first.'); return; }
  const response = await fetch(`/engagements/${engagementId}/run`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({include_active_checks: false, selected_agents: ['recon', 'api_mapper', 'authz', 'secret_review', 'risk', 'report']})
  });
  setOutput(await response.json());
}

function downloadReport(fmt) {
  if (!engagementId) { setOutput('Create an engagement first.'); return; }
  window.location = `/engagements/${engagementId}/report/${fmt}`;
}
